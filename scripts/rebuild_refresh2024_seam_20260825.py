"""Rebuild the 2024 refresh UNDER THE SEAM DISCIPLINE (F6 of the 25 Aug audit;
Magnus decided: rebuild).

Why the July refresh could not ship: `measures_updates_2024plus.xlsx` carries 1,289
rows dated 2016-2023 (recovered-archive gap-fills), and the July build ran the plain
pipeline over the merged sheet, which RECOMPUTED the published window (47,334
substantive cells adrift of the frozen files in onetsoc2010 alone). The recovered
pre-2024 rows are still wanted: they set the frontier state entering 2024, so the
2024 increment is computed against the fuller archive. What must not happen is the
published 2010-2023 levels moving. That is exactly the assembler's splice: frozen
checkpoints feed stage 4, rows through 2023 are carried verbatim, 2024 chains on the
frozen 2023 level, and the seam gates prove it.

This script is the assembler's main() restricted to the Track A refresh: year_final
2024, the one Track A workbook, no extensions, published membership, published genai.
Then the frozen-window percentile ranks are pinned to the canonical published files
(data/reference/Publication, the same files the bundle ships as frozen-2010-2023),
with a fatal byte-identity assert.

Output: data/vintage/refresh2024_seam_20260825/out (+ Publication/) and
reports/refresh2024_seam_20260825/REBUILD-REPORT.md.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daioe import config as cfgmod  # noqa: E402
from daioe import io as dio  # noqa: E402
from daioe import stage2_ai_progress as s2  # noqa: E402
from daioe import stage4_index as s4  # noqa: E402
from daioe import stage5_taxonomies as s5  # noqa: E402
from daioe import stata_ops as so  # noqa: E402

aspec = importlib.util.spec_from_file_location(
    "asm", ROOT / "scripts/assemble_vintage_2025_20260808.py")
asm = importlib.util.module_from_spec(aspec)
aspec.loader.exec_module(asm)

TAG = "refresh2024_seam_20260825"
OUT = ROOT / "data" / "vintage" / TAG / "out"
REP = ROOT / "reports" / TAG
CANON = ROOT / "data" / "reference" / "Publication"   # the shipped frozen files
FROZEN_OUT = ROOT / "data" / "out"

for d in (OUT, REP):
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)

# ---------------------------------------------------------------- config ------
raw = yaml.safe_load((ROOT / "config-refresh2024.yaml").read_text())
assert int(raw["year_final"]) == 2024, "refresh config must end at 2024"
assert raw["benchmark_updates"] == ["data/updates/measures_updates_2024plus.xlsx"], (
    "refresh is Track A only; extensions enter via the 2025 vintage")
assert not raw.get("benchmark_extensions"), "refresh admits no Track B extensions"
raw["paths"] = dict(raw["paths"])
raw["paths"]["out"] = str(OUT.relative_to(ROOT))
cfg = cfgmod.Config(raw=raw, root=ROOT)

# ------------------------------------------------- frozen checkpoints in -----
for p in FROZEN_OUT.glob("*.parquet"):
    shutil.copy(p, OUT / p.name)

print("[1/5] stage 2 (year_final 2024, Track A workbook only) ...")
s2.run(cfg, validate=False)

print("[2/5] stage 4 exposure panels ...")
panels = s4.build(cfg)

print("[3/5] splice at the 2023 seam (frozen history verbatim) ...")
frozen_prelim = pd.read_parquet(FROZEN_OUT / "daioe_panel_onet_preliminary.parquet")
spliced = asm.splice_preliminary(frozen_prelim, panels["preliminary"], cfg.app_categories)
spliced.to_parquet(OUT / "daioe_panel_onet_preliminary.parquet", index=False)

keys = ["occ_code_onet", "year"]
shared = [c for c in frozen_prelim.columns
          if c not in keys and frozen_prelim[c].dtype.kind in "fc"]
a = spliced[spliced["year"] <= 2023].set_index(keys)[shared].sort_index()
b = frozen_prelim.set_index(keys)[shared].sort_index()
assert a.index.equals(b.index), "G1 FAILED: frozen-window row set changed"
d = (a.fillna(-9e9).values != b.fillna(-9e9).values).sum()
assert d == 0, f"G1 FAILED: {int(d)} frozen preliminary cells changed"
print(f"      G1 splice integrity: {len(b)} frozen rows x {len(shared)} columns, 0 changed")

print("[4/5] stage 5 fan-out + publication exports ...")
s5.run(cfg, validate=False)

print("[5/5] seam gates + canonical rank pinning ...")
for line in asm.gate_publication_seam(OUT / "Publication"):
    print("      " + line)
for line in asm.gate_internal_seam(OUT):
    print("      internal " + line)

# Pin frozen-window pctl ranks to the canonical published files; fatal
# byte-identity assert on ALL shared daioe_/pctl columns afterwards.
TAXMAP = {
    "daioe_onetsoc2010": ["occ_code_onetsoc2010", "year"],
    "daioe_soc2010": ["occ_code_soc2010", "year"],
    "daioe_isco08": ["occ_code_isco08", "year"],
    "daioe_ssyk2012": ["ssyk2012_4", "year"],
    "daioe_ssyk96": ["ssyk96_4", "year"],
}
report = [f"# 2024 refresh rebuilt under the seam discipline ({TAG})\n"]
for stem, tkeys in TAXMAP.items():
    ref = dio.read_dta(CANON / f"{stem}.dta")
    got = dio.read_dta(OUT / "Publication" / f"{stem}.dta")
    ref_idx = ref.set_index(tkeys)
    gk = pd.MultiIndex.from_frame(got[tkeys])
    frozen_mask = got["year"] <= 2023
    n_changed = 0
    for c in [c for c in ref.columns if c.startswith("pctl_rank_") and c in got.columns]:
        target = np.asarray(gk.map(ref_idx[c]), dtype=np.float64)
        vals = got[c].to_numpy(dtype=np.float64, copy=True)
        take = frozen_mask.to_numpy() & ~np.isnan(target)
        n_changed += int((so.f32(pd.Series(vals[take])).to_numpy()
                          != so.f32(pd.Series(target[take])).to_numpy()).sum())
        vals[take] = target[take]
        got[c] = so.f32(pd.Series(vals))
    dio.write_dta(got, OUT / "Publication" / f"{stem}.dta")
    dio.write_csv_tab(got, OUT / "Publication" / f"{stem}.csv")
    dio.write_xlsx(got, OUT / "Publication" / f"{stem}.xlsx")

    chk = dio.read_dta(OUT / "Publication" / f"{stem}.dta")
    cols = [c for c in ref.columns
            if c.startswith(("daioe_", "pctl_rank_")) and c in chk.columns]
    g = chk[chk["year"] <= 2023].set_index(tkeys)[cols].sort_index()
    r = ref[ref["year"] <= 2023].set_index(tkeys)[cols].sort_index()
    assert g.index.equals(r.index), f"{stem}: frozen row sets differ"
    diff = (g.astype("float32").fillna(-9e9).values
            != r.astype("float32").fillna(-9e9).values).sum()
    assert diff == 0, f"{stem}: {int(diff)} frozen cells differ from the canonical files"
    n24 = int((chk["year"] == 2024).sum())
    report.append(f"- {stem}: frozen window byte-identical to the published files "
                  f"({len(cols)} columns; {n_changed} rank cells pinned); "
                  f"{n24} rows of 2024 appended")
    print(f"      {stem}: frozen window IDENTICAL to canon; {n24} rows of 2024")

# coverage: how many benchmarks feed 2024
fd = pd.read_parquet(OUT / "formated_data.parquet")
n_bench = fd[pd.to_datetime(fd["date"], errors="coerce").dt.year <= 2024][
    "metrics_name"].nunique()
mf = pd.read_parquet(OUT / "metrics_frontiers.parquet")
n_2024 = mf[(mf["year"] == 2024) & (mf["deltafinal"] > 0)]["metrics_name"].nunique()
report.append(f"\nBenchmark series in the merged sheet through 2024: {n_bench}; "
              f"series with a positive 2024 frontier move: {n_2024}.")
(REP / "REBUILD-REPORT.md").write_text("\n".join(report) + "\n")
print("\n".join(report))
print("\nREBUILD COMPLETE:", OUT)
