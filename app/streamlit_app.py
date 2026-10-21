"""Liquidity & ALM Risk dashboard.

Five views mirroring a Liquidity Risk / ALM team and the offer's mission:
  1. Balance sheet   - the ALM view of assets and liabilities
  2. LCR             - Liquidity Coverage Ratio, HQLA, 30-day net outflows
  3. NSFR            - Net Stable Funding Ratio, ASF vs RSF
  4. Liquidity gap   - maturity ladder and survival horizon
  5. IRRBB           - dEVE / dNII under the Basel standardised rate shocks

Runs with no data files and no token: the balance sheet is built deterministically.
"""
import os
import sys

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import balance_sheet, lcr, nsfr, liquidity_gap, irrbb

st.set_page_config(page_title="Liquidity & ALM Risk Engine", layout="wide")
NAVY = "#0d2538"

st.title("Liquidity & ALM Risk Engine")
st.caption(
    "LCR · NSFR · liquidity gap & survival horizon · IRRBB (dEVE / dNII). "
    "Regulatory liquidity metrics on a representative balance sheet, no token required."
)

a, l = balance_sheet.build_balance_sheet()

with st.sidebar:
    st.header("Capital")
    tier1 = st.number_input("Tier 1 capital (M)", value=17_000, step=1_000)
    st.header("Stress")
    retail_runoff = st.slider("Extra retail deposit run-off (pp)", 0, 20, 0,
                              help="Shock: increase retail deposit outflow in the LCR")
    st.caption(f"Balance sheet: {a['amount'].sum():,.0f}M total assets")

# apply a simple LCR stress: bump retail run-off by moving to a stressed copy
l_stressed = l.copy()

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Balance sheet", "LCR", "NSFR", "Liquidity gap", "IRRBB"]
)

# ---- 1. Balance sheet ------------------------------------------------------
with tab1:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Assets")
        st.dataframe(a[["item", "amount", "hqla_level", "liq_bucket", "repricing_bucket"]],
                     hide_index=True, use_container_width=True)
    with c2:
        st.subheader("Liabilities & equity")
        st.dataframe(l[["item", "amount", "liab_type", "liq_bucket", "repricing_bucket"]],
                     hide_index=True, use_container_width=True)
    ta, tl = balance_sheet.balance_check()
    st.metric("Balance check (assets = liabilities + equity)", f"{ta:,.0f}M = {tl:,.0f}M")

# ---- 2. LCR ----------------------------------------------------------------
with tab2:
    st.subheader("Liquidity Coverage Ratio")
    # stress: raise retail run-off by retail_runoff pp via a custom report
    lr = lcr.lcr_report(a, l)
    if retail_runoff > 0:
        extra = retail_runoff / 100.0
        retail = l[l["liab_type"].isin(["retail_stable", "retail_less_stable"])]["amount"].sum()
        stressed_net = lr["net_outflows"] + extra * retail
        stressed_lcr = lr["total_hqla"] / stressed_net
    else:
        stressed_lcr = lr["lcr"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Total HQLA", f"{lr['total_hqla']:,.0f}M")
    c2.metric("Net 30d outflows", f"{lr['net_outflows']:,.0f}M")
    c3.metric("LCR", f"{stressed_lcr*100:.0f}%",
              f"{(stressed_lcr-lr['lcr'])*100:.0f} pp" if retail_runoff else None,
              delta_color="inverse")
    st.progress(min(stressed_lcr / 2, 1.0))
    st.caption("Regulatory minimum: 100%. HQLA after haircuts and the Level 2 / 2B caps.")
    hb = lr["hqla_breakdown"]
    st.bar_chart(pd.Series(
        {"Level 1": hb["level_1"], "Level 2A": hb["level_2a"], "Level 2B": hb["level_2b_after_cap"]}
    ))

# ---- 3. NSFR ---------------------------------------------------------------
with tab3:
    st.subheader("Net Stable Funding Ratio")
    nr = nsfr.nsfr_report(a, l)
    c1, c2, c3 = st.columns(3)
    c1.metric("Available Stable Funding", f"{nr['asf']:,.0f}M")
    c2.metric("Required Stable Funding", f"{nr['rsf']:,.0f}M")
    c3.metric("NSFR", f"{nr['nsfr_pct']:.0f}%", "PASS" if nr["pass"] else "FAIL")
    st.caption("Regulatory minimum: 100%. Structural one-year funding stability.")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**ASF by source**")
        st.dataframe(nr["asf_breakdown"].round(0), hide_index=True, use_container_width=True)
    with c2:
        st.markdown("**RSF by asset**")
        st.dataframe(nr["rsf_breakdown"].round(0), hide_index=True, use_container_width=True)

# ---- 4. Liquidity gap ------------------------------------------------------
with tab4:
    st.subheader("Maturity-ladder liquidity gap")
    lr = lcr.lcr_report(a, l)
    sh = liquidity_gap.survival_horizon(a, l, lr["total_hqla"])
    ladder = sh["ladder"]
    st.metric("Survival horizon", sh["survival_horizon"])
    chart_df = ladder.set_index("bucket")[["marginal_gap", "cumulative_gap"]]
    chart_df["HQLA + cumulative"] = lr["total_hqla"] + ladder["cumulative_gap"].values
    st.line_chart(chart_df[["cumulative_gap", "HQLA + cumulative"]])
    st.bar_chart(ladder.set_index("bucket")["marginal_gap"])
    st.dataframe(ladder.round(0), hide_index=True, use_container_width=True)
    st.caption("Survival horizon: last bucket where HQLA plus the cumulative gap stays positive.")

# ---- 5. IRRBB --------------------------------------------------------------
with tab5:
    st.subheader("Interest Rate Risk in the Banking Book")
    ir = irrbb.irrbb_report(a, l, tier1_capital=tier1)
    c1, c2, c3 = st.columns(3)
    c1.metric("dNII (+100bp)", f"{ir['delta_nii_up_100bp']:,.0f}M")
    c2.metric("dNII (-100bp)", f"{ir['delta_nii_down_100bp']:,.0f}M")
    c3.metric("Worst dEVE", f"{ir['worst_eve']:,.0f}M",
              f"{ir['worst_eve_pct_tier1']:.1f}% of Tier 1", delta_color="inverse")
    sot = "BREACH" if ir["sot_breach"] else "within limit"
    st.write(f"**Supervisory Outlier Test** (dEVE vs 15% of Tier 1): **{sot}** "
             f"(worst scenario: {ir['worst_eve_scenario']}).")
    st.bar_chart(ir["delta_eve"].set_index("scenario")["delta_eve"])
    st.markdown("**Repricing gap by bucket**")
    st.dataframe(ir["repricing_gap"].round(0), hide_index=True, use_container_width=True)
    st.caption("dEVE: present-value sensitivity (long-term). dNII: 1-year earnings sensitivity.")
