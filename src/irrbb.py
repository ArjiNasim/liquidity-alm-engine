"""Interest Rate Risk in the Banking Book (IRRBB).

IRRBB measures how the banking book's value and earnings move with rates, through
two complementary metrics the Basel standards require:

  dEVE  change in Economic Value of Equity: the present-value sensitivity of all
        banking-book cash flows to a rate shock (a long-term, value view).
  dNII  change in Net Interest Income: the 1-year earnings sensitivity from the
        repricing gap (a short-term, earnings view).

The six Basel standardised interest-rate shock scenarios are applied, and dEVE is
checked against the Supervisory Outlier Test threshold (15% of Tier 1 capital).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .balance_sheet import BUCKET_NAMES, BUCKET_MIDS

__all__ = ["BASEL_SHOCKS", "repricing_gap", "delta_nii", "delta_eve", "irrbb_report"]

# Six Basel standardised shocks, as bp functions of bucket midpoint (simplified).
# Parallel: +/-200bp. Short: +/-250bp decaying with tenor. Steepener/flattener mix.
def _shock_curve(name, t):
    bp = {
        "parallel_up":   +200,
        "parallel_down": -200,
        "short_up":      +250 * np.exp(-t / 4),
        "short_down":    -250 * np.exp(-t / 4),
        "steepener":     -65 * np.exp(-t / 4) + 90 * (1 - np.exp(-t / 4)),
        "flattener":     +80 * np.exp(-t / 4) - 60 * (1 - np.exp(-t / 4)),
    }[name]
    return bp / 1e4  # bp -> decimal

BASEL_SHOCKS = ["parallel_up", "parallel_down", "short_up", "short_down", "steepener", "flattener"]


def repricing_gap(assets: pd.DataFrame, liabilities: pd.DataFrame) -> pd.DataFrame:
    """Rate-sensitive asset minus liability notional by repricing bucket."""
    ra = assets.groupby("repricing_bucket")["amount"].sum().reindex(BUCKET_NAMES, fill_value=0)
    rl = liabilities.groupby("repricing_bucket")["amount"].sum().reindex(BUCKET_NAMES, fill_value=0)
    gap = ra - rl
    return pd.DataFrame({
        "bucket": BUCKET_NAMES,
        "rate_sensitive_assets": ra.values,
        "rate_sensitive_liabilities": rl.values,
        "repricing_gap": gap.values,
    })


def delta_nii(assets: pd.DataFrame, liabilities: pd.DataFrame, shock_bp=100) -> float:
    """1-year NII sensitivity to a parallel shock, from the <=1Y repricing gap.

    Only cash flows repricing within one year affect NII over the next year;
    each bucket's gap earns the shock for the fraction of the year it is open.
    """
    gap = repricing_gap(assets, liabilities)
    shock = shock_bp / 1e4
    within_1y = ["overnight", "1W", "1M", "3M", "6M", "1Y"]
    dnii = 0.0
    for _, row in gap.iterrows():
        if row["bucket"] in within_1y:
            t = BUCKET_MIDS[row["bucket"]]
            dnii += row["repricing_gap"] * shock * max(1.0 - t, 0.0)
    return float(dnii)


def _pv_cashflows(items: pd.DataFrame, shock_name=None) -> float:
    """Present value of a book, optionally under a shock to the discount curve."""
    base_rate = 0.03
    pv = 0.0
    for _, row in items.iterrows():
        t = BUCKET_MIDS[row["repricing_bucket"]]
        r = base_rate + (_shock_curve(shock_name, t) if shock_name else 0.0)
        pv += row["amount"] / (1 + r) ** t
    return pv


def delta_eve(assets: pd.DataFrame, liabilities: pd.DataFrame) -> pd.DataFrame:
    """dEVE under each Basel shock = change in (PV assets - PV liabilities)."""
    base = _pv_cashflows(assets) - _pv_cashflows(liabilities)
    rows = []
    for sh in BASEL_SHOCKS:
        shocked = _pv_cashflows(assets, sh) - _pv_cashflows(liabilities, sh)
        rows.append({"scenario": sh, "delta_eve": shocked - base})
    return pd.DataFrame(rows)


def irrbb_report(assets: pd.DataFrame, liabilities: pd.DataFrame, tier1_capital: float) -> dict:
    eve = delta_eve(assets, liabilities)
    worst = eve.loc[eve["delta_eve"].idxmin()]
    sot_threshold = -0.15 * tier1_capital  # Supervisory Outlier Test
    return {
        "repricing_gap": repricing_gap(assets, liabilities),
        "delta_nii_up_100bp": delta_nii(assets, liabilities, +100),
        "delta_nii_down_100bp": delta_nii(assets, liabilities, -100),
        "delta_eve": eve,
        "worst_eve_scenario": worst["scenario"],
        "worst_eve": float(worst["delta_eve"]),
        "sot_threshold": sot_threshold,
        "sot_breach": bool(worst["delta_eve"] < sot_threshold),
        "worst_eve_pct_tier1": 100 * worst["delta_eve"] / tier1_capital,
    }
