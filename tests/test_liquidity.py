"""Unit tests for the liquidity & ALM engine."""
import numpy as np
import pytest

from src import balance_sheet, lcr, nsfr, liquidity_gap, irrbb


@pytest.fixture
def bs():
    return balance_sheet.build_balance_sheet()


# ---- balance sheet ---------------------------------------------------------
def test_balance_sheet_balances():
    ta, tl = balance_sheet.balance_check()
    assert ta == pytest.approx(tl, rel=1e-9)


def test_buckets_valid(bs):
    a, l = bs
    valid = set(balance_sheet.BUCKET_NAMES)
    assert set(a["liq_bucket"]).issubset(valid)
    assert set(l["repricing_bucket"]).issubset(valid)


# ---- LCR -------------------------------------------------------------------
def test_hqla_caps(bs):
    a, _ = bs
    h = lcr.hqla(a)
    # Level 2 after cap cannot exceed 2/3 of Level 1 (40%/60% rule)
    assert h["level_2_after_cap"] <= (40 / 60) * h["level_1"] + 1e-6
    assert h["total_hqla"] > 0


def test_lcr_positive_and_reasonable(bs):
    a, l = bs
    rep = lcr.lcr_report(a, l)
    assert rep["lcr"] > 0
    assert rep["net_outflows"] > 0
    # inflows capped at 75% of outflows
    assert rep["capped_inflows"] <= 0.75 * rep["gross_outflows"] + 1e-6


def test_lcr_falls_when_deposits_flee(bs):
    a, l = bs
    base = lcr.lcr_ratio(a, l)
    stressed = l.copy()
    # convert stable retail to financial (100% runoff) -> LCR must drop
    stressed.loc[stressed["liab_type"] == "retail_stable", "liab_type"] = "wholesale_fi"
    worse = lcr.lcr_ratio(a, stressed)
    assert worse < base


# ---- NSFR ------------------------------------------------------------------
def test_nsfr_positive(bs):
    a, l = bs
    rep = nsfr.nsfr_report(a, l)
    assert rep["asf"] > 0 and rep["rsf"] > 0
    assert rep["nsfr"] > 0


def test_nsfr_improves_with_more_capital(bs):
    a, l = bs
    base = nsfr.nsfr_ratio(a, l)
    more = l.copy()
    more.loc[more["liab_type"] == "capital", "amount"] *= 1.5  # more 100% ASF
    assert nsfr.nsfr_ratio(a, more) > base


# ---- liquidity gap ---------------------------------------------------------
def test_ladder_cumulative(bs):
    a, l = bs
    ladder = liquidity_gap.maturity_ladder(a, l)
    # cumulative gap is the running sum of marginal gaps
    assert ladder["cumulative_gap"].iloc[-1] == pytest.approx(ladder["marginal_gap"].sum())


def test_survival_horizon_runs(bs):
    a, l = bs
    h = lcr.hqla(a)["total_hqla"]
    res = liquidity_gap.survival_horizon(a, l, h)
    assert "survival_horizon" in res
    assert res["ladder"].shape[0] == len(balance_sheet.BUCKET_NAMES)


# ---- IRRBB -----------------------------------------------------------------
def test_repricing_gap_sums(bs):
    a, l = bs
    g = irrbb.repricing_gap(a, l)
    assert g["repricing_gap"].sum() == pytest.approx(
        a["amount"].sum() - l["amount"].sum(), abs=1e-6
    )


def test_delta_nii_sign(bs):
    a, l = bs
    up = irrbb.delta_nii(a, l, +100)
    down = irrbb.delta_nii(a, l, -100)
    # symmetric shocks give opposite-sign NII impact
    assert np.sign(up) == -np.sign(down) or up == 0


def test_delta_eve_parallel_opposite(bs):
    a, l = bs
    eve = irrbb.delta_eve(a, l).set_index("scenario")["delta_eve"]
    # a parallel up and down should move EVE in opposite directions
    assert np.sign(eve["parallel_up"]) == -np.sign(eve["parallel_down"])


def test_irrbb_report_sot(bs):
    a, l = bs
    rep = irrbb.irrbb_report(a, l, tier1_capital=17_000)
    assert rep["worst_eve"] <= 0
    assert "sot_breach" in rep
    assert rep["sot_threshold"] < 0
