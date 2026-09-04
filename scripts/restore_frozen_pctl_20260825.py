"""F1(b) of the 25 Aug audit (Magnus: option (c)): make the v1.1.0 release
candidate's frozen-window percentile ranks byte-identical to the v1.0.0 release's
frozen files.

Background (notes/AUDIT-described-vs-implemented_2026-08-25.md, F1): the v1.0.0
frozen files are the original Stata exports; the pipeline's own frozen build agrees
with them exactly on every substantive daioe_* value but assigns order-dependent
percentile ranks differently inside tie groups. Left alone, a user diffing v1.1.0
against v1.0.0 would find tens of thousands of changed pctl_rank_* cells in the
window both releases call frozen. This script restores the shipped ranks so that
diff is empty.

What it does, per publication taxonomy: overwrite year<=2023 values of every
pctl_rank_* column THAT EXISTS IN v1.0.0 with the v1.0.0 values, matched on
(key, year); columns new in v1.1.0 (pctl_rank_g2all/agentic/mathsci) are untouched,
as are all daioe_* columns (verified identical before and after) and all years
beyond 2023. Rewrites .dta/.csv/.xlsx like the wiring script. Fatal verification at
the end: the candidate's frozen window equals the v1.0.0 frozen files exactly at
float32 on ALL shared daioe_* and pctl_rank_* columns.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from daioe import io as dio  # noqa: E402
from daioe import stata_ops as so  # noqa: E402

DIST = ROOT / "dist/daioe-v1.0.0-scores/frozen-2010-2023"
import sys
PUB = (Path(sys.argv[1]) if len(sys.argv) > 1
       else ROOT / "data/vintage/vintage_2025_v110rc_20260824/out/Publication")
TAXMAP = {
    "daioe_onetsoc2010": ["occ_code_onetsoc2010", "year"],
    "daioe_soc2010": ["occ_code_soc2010", "year"],
    "daioe_isco08": ["occ_code_isco08", "year"],
    "daioe_ssyk2012": ["ssyk2012_4", "year"],
    "daioe_ssyk96": ["ssyk96_4", "year"],
}

for stem, keys in TAXMAP.items():
    ref = dio.read_dta(DIST / f"{stem}.dta")
    got = dio.read_dta(PUB / f"{stem}.dta")
    pcols = [c for c in ref.columns if c.startswith("pctl_rank_") and c in got.columns]
    ref_idx = ref.set_index(keys)
    frozen_mask = got["year"] <= 2023
    gk = pd.MultiIndex.from_frame(got[keys])
    n_changed = 0
    for c in pcols:
        target = gk.map(ref_idx[c])
        vals = got[c].to_numpy(dtype=np.float64, copy=True)
        new = np.asarray(target, dtype=np.float64)
        take = frozen_mask.to_numpy() & ~np.isnan(new)
        n_changed += int((so.f32(pd.Series(vals[take])).to_numpy()
                          != so.f32(pd.Series(new[take])).to_numpy()).sum())
        vals[take] = new[take]
        got[c] = so.f32(pd.Series(vals))
    dio.write_dta(got, PUB / f"{stem}.dta")
    dio.write_csv_tab(got, PUB / f"{stem}.csv")
    dio.write_xlsx(got, PUB / f"{stem}.xlsx")

    # fatal verification: frozen window equals v1.0.0 exactly on all shared columns
    chk = dio.read_dta(PUB / f"{stem}.dta")
    cols = [c for c in ref.columns
            if c.startswith(("daioe_", "pctl_rank_")) and c in chk.columns]
    g = chk[chk["year"] <= 2023].set_index(keys)[cols].sort_index()
    r = ref[ref["year"] <= 2023].set_index(keys)[cols].sort_index()
    assert g.index.equals(r.index), f"{stem}: row sets differ"
    diff = (g.astype("float32").fillna(-9e9).values
            != r.astype("float32").fillna(-9e9).values).sum()
    assert diff == 0, f"{stem}: {int(diff)} cells still differ from v1.0.0"
    print(f"{stem}: {n_changed} pctl cells restored; frozen window now IDENTICAL "
          f"to v1.0.0 on {len(cols)} shared columns")
print("F1(b) complete: v1.1.0 rc frozen window byte-identical to v1.0.0 at float32.")
