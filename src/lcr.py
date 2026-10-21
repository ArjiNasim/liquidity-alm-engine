"""Liquidity Coverage Ratio (Basel III LCR).

The LCR ensures a bank holds enough High-Quality Liquid Assets (HQLA) to survive
a 30-day stress:

    LCR = HQLA / net cash outflows over 30 days  >= 100%

HQLA is tiered with haircuts and caps:
  Level 1   no haircut, no cap            (cash, reserves, Level 1 sovereigns)
  Level 2A  15% haircut                   (covered/PSE bonds)
  Level 2B  25-50% haircut                (lower-rated corporates, etc.)
  Level 2 total capped at 40% of HQLA; Level 2B capped at 15% of HQLA.

Net outflows = stressed outflows - min(stressed inflows, 75% of outflows).
Run-off and inflow rates follow the Basel LCR standard.
"""
from __future__ import annotations

import pandas as pd

__all__ = ["hqla", "cash_outflows", "cash_inflows", "lcr_ratio", "lcr_report"]

# HQLA haircuts by level code used in the balance sheet (1, 2.0 = L2A, 2.5 = L2B)
_HAIRCUT = {1: 0.00, 2.0: 0.15, 2.5: 0.50}

# Outflow run-off rates by liability type (30-day stressed)
_OUTFLOW_RATE = {
    "retail_stable": 0.05,
    "retail_less_stable": 0.10,
    "wholesale_op": 0.25,       # operational deposits
    "wholesale_corp": 0.40,     # non-operational corporate
    "wholesale_fi": 1.00,       # financial institutions
    "secured_funding": 0.25,    # repo backed by non-L1 collateral (simplified)
    "debt_long": 0.00,          # >30d maturity, no 30-day outflow
    "capital": 0.00,
}
# Inflow rates on maturing assets within 30 days
_INFLOW_RATE = {
    "Interbank placements": 1.00,
    "Reverse repo (secured)": 1.00,
    "Corporate loans": 0.50,
    "Retail consumer loans": 0.50,
}
_SHORT_BUCKETS = {"overnight", "1W", "1M"}


def hqla(assets: pd.DataFrame):
    """Total HQLA after haircuts and the Level 2 / Level 2B caps."""
    df = assets.copy()
    df = df[df["hqla_level"] > 0]
    df["haircut"] = df["hqla_level"].map(_HAIRCUT)
    df["post_haircut"] = df["amount"] * (1 - df["haircut"])
    l1 = df.loc[df["hqla_level"] == 1, "post_haircut"].sum()
    l2a = df.loc[df["hqla_level"] == 2.0, "post_haircut"].sum()
    l2b = df.loc[df["hqla_level"] == 2.5, "post_haircut"].sum()
    # Caps: Level 2 <= 40% of total HQLA; Level 2B <= 15% of total HQLA.
    # Apply iteratively on the adjusted stock (standard formula).
    l2b_capped = min(l2b, (15 / 85) * (l1 + l2a))
    l2_total = l2a + l2b_capped
    l2_capped = min(l2_total, (40 / 60) * l1)
    total = l1 + l2_capped
    return {
        "level_1": float(l1),
        "level_2a": float(l2a),
        "level_2b_after_cap": float(l2b_capped),
        "level_2_after_cap": float(l2_capped),
        "total_hqla": float(total),
    }


def cash_outflows(liabilities: pd.DataFrame) -> float:
    """Total stressed 30-day cash outflows."""
    df = liabilities.copy()
    df["rate"] = df["liab_type"].map(_OUTFLOW_RATE).fillna(0.0)
    df["outflow"] = df["amount"] * df["rate"]
    return float(df["outflow"].sum())


def cash_inflows(assets: pd.DataFrame) -> float:
    """Total 30-day cash inflows from maturing/short assets."""
    df = assets.copy()
    df["rate"] = df["item"].map(_INFLOW_RATE).fillna(0.0)
    # only count inflows from assets maturing within 30 days
    df.loc[~df["liq_bucket"].isin(_SHORT_BUCKETS), "rate"] = df["rate"] * 0.0
    df["inflow"] = df["amount"] * df["rate"]
    return float(df["inflow"].sum())


def lcr_ratio(assets: pd.DataFrame, liabilities: pd.DataFrame) -> float:
    h = hqla(assets)["total_hqla"]
    out = cash_outflows(liabilities)
    inf = cash_inflows(assets)
    net_out = max(out - min(inf, 0.75 * out), 0.0)
    return h / net_out if net_out else float("inf")


def lcr_report(assets: pd.DataFrame, liabilities: pd.DataFrame) -> dict:
    h = hqla(assets)
    out = cash_outflows(liabilities)
    inf = cash_inflows(assets)
    capped_inflows = min(inf, 0.75 * out)
    net_out = max(out - capped_inflows, 0.0)
    ratio = h["total_hqla"] / net_out if net_out else float("inf")
    return {
        "total_hqla": h["total_hqla"],
        "hqla_breakdown": h,
        "gross_outflows": out,
        "gross_inflows": inf,
        "capped_inflows": capped_inflows,
        "net_outflows": net_out,
        "lcr": ratio,
        "lcr_pct": ratio * 100,
        "pass": ratio >= 1.0,
    }
