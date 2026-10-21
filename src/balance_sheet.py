"""A representative bank balance sheet for liquidity and ALM analysis.

Liquidity and ALM work off the balance sheet: the asset and liability items, their
maturities, their behavioural runoff, and their rate-repricing dates. Real
balance-sheet data is confidential, so this module builds a deterministic,
seeded balance sheet calibrated to a mid-to-large commercial bank, detailed
enough to compute the LCR, the NSFR, a maturity-ladder liquidity gap and the
IRRBB sensitivities.

All amounts are in millions of reporting currency.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["TIME_BUCKETS", "build_balance_sheet", "assets_table", "liabilities_table"]

# Maturity / repricing buckets (midpoint in years used for discounting)
TIME_BUCKETS = [
    ("overnight", 1 / 365),
    ("1W", 7 / 365),
    ("1M", 1 / 12),
    ("3M", 0.25),
    ("6M", 0.5),
    ("1Y", 1.0),
    ("2Y", 2.0),
    ("5Y", 4.0),
    (">5Y", 8.0),
]
BUCKET_NAMES = [b[0] for b in TIME_BUCKETS]
BUCKET_MIDS = {b[0]: b[1] for b in TIME_BUCKETS}


def _asset_rows():
    # item, amount, HQLA level (0=non-HQLA), liquidity bucket, rate-repricing bucket, fixed_rate
    return [
        ("Cash & central bank reserves",   12_000, 1, "overnight", "overnight", 0.0),
        ("Level 1 sovereign bonds",        28_000, 1, ">5Y",        "overnight", 0.030),
        ("Level 2A covered/PSE bonds",      9_000, 2.0, "2Y",       "1Y",        0.035),
        ("Level 2B corporate bonds",        4_000, 2.5, "5Y",       "1Y",        0.045),
        ("Interbank placements",            6_000, 0, "1M",         "1M",        0.028),
        ("Retail mortgages",               45_000, 0, ">5Y",        "2Y",        0.041),
        ("Retail consumer loans",          14_000, 0, "2Y",         "1Y",        0.075),
        ("Corporate loans",                38_000, 0, "5Y",         "3M",        0.050),
        ("Reverse repo (secured)",          8_000, 0, "1W",         "overnight", 0.026),
        ("Fixed assets & other",            6_000, 0, ">5Y",        ">5Y",       0.0),
    ]


def _liability_rows():
    # item, amount, liability type, liquidity bucket, rate-repricing bucket, fixed_rate
    return [
        # Non-maturing deposits: behavioural liquidity bucket (sticky core), but
        # repricing is immediate (they reprice at the bank's discretion).
        ("Retail deposits - stable",       52_000, "retail_stable",      "5Y",        "overnight", 0.015),
        ("Retail deposits - less stable",  20_000, "retail_less_stable", "1Y",        "overnight", 0.018),
        ("SME operational deposits",       14_000, "wholesale_op",       "1M",        "overnight", 0.020),
        ("Corporate non-op deposits",      28_000, "wholesale_corp",     "3M",        "3M",        0.030),
        ("Financial institution deposits", 10_000, "wholesale_fi",       "1M",        "1M",        0.034),
        ("Senior unsecured debt",          15_000, "debt_long",          "5Y",        "1Y",        0.042),
        ("Repo funding (secured)",          9_000, "secured_funding",    "1W",        "overnight", 0.027),
        ("Interbank borrowing",             5_000, "wholesale_fi",       "1W",        "overnight", 0.033),
        ("Equity & reserves",              17_000, "capital",            ">5Y",       ">5Y",       0.0),
    ]


def build_balance_sheet(seed: int | None = None):
    """Return (assets_df, liabilities_df). `seed` left for API symmetry; data is fixed."""
    a = pd.DataFrame(
        _asset_rows(),
        columns=["item", "amount", "hqla_level", "liq_bucket", "repricing_bucket", "rate"],
    )
    l = pd.DataFrame(
        _liability_rows(),
        columns=["item", "amount", "liab_type", "liq_bucket", "repricing_bucket", "rate"],
    )
    return a, l


def assets_table():
    return build_balance_sheet()[0]


def liabilities_table():
    return build_balance_sheet()[1]


def balance_check():
    """Total assets vs total liabilities+equity (should balance)."""
    a, l = build_balance_sheet()
    return float(a["amount"].sum()), float(l["amount"].sum())
