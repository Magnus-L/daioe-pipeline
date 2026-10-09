"""The robotics series (`roe`) must not ship as a time series (9 Oct 2026).

`roe` has no progress series behind it: one expert-elicited ability mapping, entered
as a unit step in the build's final year. The v1.1.0 vintage repeats that step in
2025, so `exp_cumul_roe` doubles from 2023 to 2025 with no change in any ranking
(DOCUMENTATION.md Section 1; VINTAGES.md, Known caveats).

The first test pins the documented numbers on the released bundle, so the
documentation cannot drift from the files. The second is the guard for the next
release: it is a strict xfail today and turns into a failure the moment the fix
lands (roe as a single cross-section), which is the signal to drop the xfail.
"""
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "dist" / "daioe-v1.1.0-scores"
FROZEN = BUNDLE / "soc2018" / "daioe_panel_soc2018.dta"
VINTAGE = BUNDLE / "vintage-2025" / "soc2018" / "daioe_panel_soc2018.dta"
NEXT_VINTAGE = (ROOT / "data" / "vintage" / "vintage_2025_v110rc3_20260905" / "out"
                / "daioe_panel_soc2018.dta")

needs_bundle = pytest.mark.skipif(not VINTAGE.exists(), reason="v1.1.0 bundle not built locally")


def _years_with_roe(path):
    d = pd.read_stata(path)
    return d, sorted(d.loc[d["exp_cumul_roe"].notna(), "year"].unique())


@needs_bundle
def test_released_roe_matches_documentation():
    frozen, fy = _years_with_roe(FROZEN)
    assert fy == [2023.0], "frozen panel: roe populated in 2023 only"

    vint, _ = _years_with_roe(VINTAGE)
    m = vint.groupby("year")["exp_cumul_roe"].mean()
    assert round(m[2023.0], 3) == 0.314 and round(m[2025.0], 3) == 0.629
    # the doubling carries no ranking information
    sd = vint.dropna(subset=["pctl_mid_roe"]).groupby("SOC2018code")["pctl_mid_roe"].std()
    assert sd.max() == 0.0


@pytest.mark.skipif(not NEXT_VINTAGE.exists(), reason="vintage build not present locally")
@pytest.mark.xfail(strict=True, reason="known v1.1.0 defect: roe step repeated in 2025; "
                   "fix = ship roe as one cross-section, then delete this xfail")
def test_next_release_roe_is_time_invariant():
    d, years = _years_with_roe(NEXT_VINTAGE)
    assert len(years) <= 1, f"roe populated in {years}: a constant read as a time series"
