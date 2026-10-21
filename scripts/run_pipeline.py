"""End-to-end liquidity & ALM pipeline: balance sheet -> LCR -> NSFR ->
liquidity gap / survival horizon -> IRRBB. Prints a full report and saves the
balance sheet to data/balance_sheet.parquet.

Run:  python scripts/run_pipeline.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import balance_sheet, lcr, nsfr, liquidity_gap, irrbb


def main():
    print(f"\n{'='*64}\nLIQUIDITY & ALM REPORT\n{'='*64}")
    a, l = balance_sheet.build_balance_sheet()
    ta, tl = balance_sheet.balance_check()
    print(f"Total assets: {ta:,.0f}M   Total liabilities+equity: {tl:,.0f}M\n")

    print("LIQUIDITY COVERAGE RATIO (LCR):")
    lr = lcr.lcr_report(a, l)
    print(f"  Total HQLA        : {lr['total_hqla']:,.0f}M")
    print(f"  Net 30d outflows  : {lr['net_outflows']:,.0f}M")
    print(f"  LCR               : {lr['lcr_pct']:.0f}%   ({'PASS' if lr['pass'] else 'FAIL'}, min 100%)")

    print("\nNET STABLE FUNDING RATIO (NSFR):")
    nr = nsfr.nsfr_report(a, l)
    print(f"  ASF               : {nr['asf']:,.0f}M")
    print(f"  RSF               : {nr['rsf']:,.0f}M")
    print(f"  NSFR              : {nr['nsfr_pct']:.0f}%   ({'PASS' if nr['pass'] else 'FAIL'}, min 100%)")

    print("\nLIQUIDITY GAP (maturity ladder):")
    h = lr["total_hqla"]
    sh = liquidity_gap.survival_horizon(a, l, h)
    print(sh["ladder"][["bucket", "marginal_gap", "cumulative_gap"]].to_string(index=False))
    print(f"  Survival horizon  : {sh['survival_horizon']}")

    print("\nIRRBB (interest rate risk in the banking book):")
    ir = irrbb.irrbb_report(a, l, tier1_capital=17_000)
    print(f"  dNII (+100bp)     : {ir['delta_nii_up_100bp']:,.0f}M")
    print(f"  dNII (-100bp)     : {ir['delta_nii_down_100bp']:,.0f}M")
    print("  dEVE by scenario:")
    print(ir["delta_eve"].to_string(index=False))
    print(f"  Worst dEVE        : {ir['worst_eve']:,.0f}M ({ir['worst_eve_scenario']}, "
          f"{ir['worst_eve_pct_tier1']:.1f}% of Tier 1)")
    print(f"  SOT breach (>15%) : {ir['sot_breach']}")

    os.makedirs("data", exist_ok=True)
    a.to_parquet("data/balance_sheet.parquet")
    print(f"\nSaved data/balance_sheet.parquet\n{'='*64}")


if __name__ == "__main__":
    main()
