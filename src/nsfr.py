"""Net Stable Funding Ratio (Basel III NSFR).

The NSFR is the structural, one-year companion to the LCR: it checks that
long-term and illiquid assets are funded by stable sources.

    NSFR = Available Stable Funding (ASF) / Required Stable Funding (RSF) >= 100%

ASF weights liabilities and capital by how stable the funding is (capital and
long-term debt 100%, stable retail 95%, less stable retail 90%, operational and
corporate wholesale 50%, short financial 0%). RSF weights assets by how much
stable funding they need (cash 0%, Level 1 5%, Level 2A 15%, Level 2B 50%,
loans 65-85%, other assets 100%).
"""
from __future__ import annotations

import pandas as pd

__all__ = ["available_stable_funding", "required_stable_funding", "nsfr_ratio", "nsfr_report"]

# ASF factors by liability type
_ASF = {
    "capital": 1.00,
    "debt_long": 1.00,          # effective maturity >= 1y
    "retail_stable": 0.95,
    "retail_less_stable": 0.90,
    "wholesale_op": 0.50,
    "wholesale_corp": 0.50,
    "wholesale_fi": 0.00,       # short-term financial funding
    "secured_funding": 0.00,
}

# RSF factors by balance-sheet item
_RSF = {
    "Cash & central bank reserves": 0.00,
    "Level 1 sovereign bonds": 0.05,
    "Level 2A covered/PSE bonds": 0.15,
    "Level 2B corporate bonds": 0.50,
    "Interbank placements": 0.15,
    "Retail mortgages": 0.65,
    "Retail consumer loans": 0.85,
    "Corporate loans": 0.85,
    "Reverse repo (secured)": 0.10,
    "Fixed assets & other": 1.00,
}


def available_stable_funding(liabilities: pd.DataFrame) -> float:
    df = liabilities.copy()
    df["factor"] = df["liab_type"].map(_ASF).fillna(0.5)
    df["asf"] = df["amount"] * df["factor"]
    return float(df["asf"].sum())


def required_stable_funding(assets: pd.DataFrame) -> float:
    df = assets.copy()
    df["factor"] = df["item"].map(_RSF).fillna(0.85)
    df["rsf"] = df["amount"] * df["factor"]
    return float(df["rsf"].sum())


def nsfr_ratio(assets: pd.DataFrame, liabilities: pd.DataFrame) -> float:
    asf = available_stable_funding(liabilities)
    rsf = required_stable_funding(assets)
    return asf / rsf if rsf else float("inf")


def nsfr_report(assets: pd.DataFrame, liabilities: pd.DataFrame) -> dict:
    asf = available_stable_funding(liabilities)
    rsf = required_stable_funding(assets)
    ratio = asf / rsf if rsf else float("inf")
    # breakdowns for the dashboard
    la = liabilities.copy()
    la["factor"] = la["liab_type"].map(_ASF).fillna(0.5)
    la["asf"] = la["amount"] * la["factor"]
    aa = assets.copy()
    aa["factor"] = aa["item"].map(_RSF).fillna(0.85)
    aa["rsf"] = aa["amount"] * aa["factor"]
    return {
        "asf": asf,
        "rsf": rsf,
        "nsfr": ratio,
        "nsfr_pct": ratio * 100,
        "pass": ratio >= 1.0,
        "asf_breakdown": la[["item", "amount", "factor", "asf"]],
        "rsf_breakdown": aa[["item", "amount", "factor", "rsf"]],
    }
