"""Maturity-ladder liquidity gap and survival horizon.

The liquidity gap places every asset inflow and liability outflow in its maturity
bucket and nets them. The cumulative gap, combined with the stock of liquid
assets (the counterbalancing capacity), gives the survival horizon: how long the
bank can meet its obligations under its contractual/behavioural profile before
liquidity runs out.

  marginal gap(bucket)   = asset inflows - liability outflows in that bucket
  cumulative gap(bucket) = running sum of marginal gaps
  counterbalancing       = HQLA stock available to plug negative gaps
  survival horizon       = last bucket where HQLA + cumulative gap stays >= 0
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .balance_sheet import BUCKET_NAMES

__all__ = ["maturity_ladder", "survival_horizon"]


def maturity_ladder(assets: pd.DataFrame, liabilities: pd.DataFrame) -> pd.DataFrame:
    """Marginal and cumulative liquidity gap by maturity bucket."""
    inflow = assets.groupby("liq_bucket")["amount"].sum().reindex(BUCKET_NAMES, fill_value=0)
    outflow = liabilities.groupby("liq_bucket")["amount"].sum().reindex(BUCKET_NAMES, fill_value=0)
    gap = inflow - outflow
    df = pd.DataFrame({
        "bucket": BUCKET_NAMES,
        "asset_inflow": inflow.values,
        "liability_outflow": outflow.values,
        "marginal_gap": gap.values,
    })
    df["cumulative_gap"] = df["marginal_gap"].cumsum()
    return df


def survival_horizon(assets: pd.DataFrame, liabilities: pd.DataFrame, hqla_stock: float) -> dict:
    """First bucket where HQLA + cumulative gap turns negative."""
    ladder = maturity_ladder(assets, liabilities)
    ladder["counterbalanced"] = hqla_stock + ladder["cumulative_gap"]
    breach = ladder[ladder["counterbalanced"] < 0]
    if breach.empty:
        horizon = "beyond all buckets"
        breach_bucket = None
    else:
        breach_bucket = breach.iloc[0]["bucket"]
        idx = ladder.index[ladder["bucket"] == breach_bucket][0]
        horizon = BUCKET_NAMES[idx - 1] if idx > 0 else "immediate"
    return {
        "ladder": ladder,
        "hqla_stock": hqla_stock,
        "survival_horizon": horizon,
        "first_breach_bucket": breach_bucket,
        "min_counterbalanced": float(ladder["counterbalanced"].min()),
    }
