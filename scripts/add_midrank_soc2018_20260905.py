"""Add tie-invariant midrank percentile companions to the SOC 2018 export.

The SOC 2018 panel ships as a labelled extra outside the publication format,
and until 5 Sep 2026 it was the only shipped panel without percentile
companions -- a process artefact, not a justified difference. This adds a
pctl_mid_<app> companion for every exp_cumul_<app> column: within-year midrank
percentile (average rank of the tied group over the number of non-missing
codes, times 100), the same convention as the publication panels' pctl_mid_*
columns. Self-verifies tie-invariance before writing.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "data" / "out" / "daioe_panel_soc2018.dta"
d = pd.read_stata(F)
cum = [c for c in d.columns if c.startswith("exp_cumul_")]
if "exp_cumul" in d.columns and "pctl_mid_allapps" not in d.columns:
    r = d.groupby("year")["exp_cumul"].rank(method="average")
    n = d.groupby("year")["exp_cumul"].transform("count")
    d["pctl_mid_allapps"] = (100.0 * r / n).astype("float32")
    chk = d.groupby(["year", "exp_cumul"])["pctl_mid_allapps"].nunique()
    assert (chk <= 1).all(), "tie-invariance failed for pctl_mid_allapps" 
added = []
for c in cum:
    out = "pctl_mid_" + c.removeprefix("exp_cumul_")
    if out in d.columns:
        continue
    r = d.groupby("year")[c].rank(method="average")
    n = d.groupby("year")[c].transform("count")
    d[out] = (100.0 * r / n).astype("float32")
    # tie-invariance: identical values share identical percentiles within a year
    chk = d.groupby(["year", c])[out].nunique()
    assert (chk <= 1).all(), f"tie-invariance failed for {out}"
    added.append(out)
d.to_stata(F, write_index=False)
print(f"{F.name}: {len(added)} pctl_mid_* companions added, tie-invariance verified")
