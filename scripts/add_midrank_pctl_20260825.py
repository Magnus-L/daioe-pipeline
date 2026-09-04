"""Add tie-invariant midrank percentile columns to the v1.1.0 publication panels
(decision Magnus, 25 Aug 2026, closing cross-vendor finding 5's structural half).

The legacy `pctl_rank_*` columns are the published artifact and stay frozen; their
tie convention is historical row order, so identical substantive values can carry
different ranks. The new `pctl_mid_*` columns are the tie-invariant companion: for
every `daioe_*` column, the within-year midrank percentile

    pctl_mid = 100 * average_rank(value) / N_nonmissing   (ascending; ties share
    their group's average rank, so identical values get identical percentiles)

computed over the full window. In an all-tie year every occupation sits at
100*(N+1)/(2N), i.e. about 50, instead of an arbitrary spread. Missing substantive
values get missing percentiles. New columns are outside the freeze claim by the
scope stated in VINTAGES.md.

Runs on the v1.1.0 release candidate's five publication panels and rewrites
.dta/.csv/.xlsx. Idempotent: recomputing replaces the same columns.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from daioe import io as dio  # noqa: E402
from daioe import stata_ops as so  # noqa: E402

import sys
PUB = (Path(sys.argv[1]) if len(sys.argv) > 1
       else ROOT / "data/vintage/vintage_2025_v110rc_20260824/out/Publication")
STEMS = ["daioe_onetsoc2010", "daioe_soc2010", "daioe_isco08",
         "daioe_ssyk2012", "daioe_ssyk96"]

for stem in STEMS:
    p = dio.read_dta(PUB / f"{stem}.dta")
    idx_cols = [c for c in p.columns if c.startswith("daioe_")]
    for c in idx_cols:
        p[f"pctl_mid_{c[len('daioe_'):]}"] = so.f32(
            p.groupby("year")[c].rank(method="average", pct=True) * 100.0)
    dio.write_dta(p, PUB / f"{stem}.dta")
    dio.write_csv_tab(p, PUB / f"{stem}.csv")
    dio.write_xlsx(p, PUB / f"{stem}.xlsx")

    # verification: tie-invariance (identical values share a percentile) and the
    # all-tie behaviour, checked on the known all-tie case where present
    chk = dio.read_dta(PUB / f"{stem}.dta")
    for c in idx_cols:
        m = f"pctl_mid_{c[len('daioe_'):]}"
        g = chk[[c, m, "year"]].dropna()
        nun = g.groupby(["year", c])[m].nunique()
        assert (nun <= 1).all(), f"{stem}/{m}: tied values with different percentiles"
    if "daioe_readcompr" in chk.columns:
        y13 = chk[(chk.year == 2013)]["pctl_mid_readcompr"].dropna()
        assert y13.nunique() <= 1, f"{stem}: 2013 all-tie year not constant"
    print(f"{stem}: {len(idx_cols)} pctl_mid_* columns added, tie-invariance verified")
print("MIDRANKS COMPLETE")
