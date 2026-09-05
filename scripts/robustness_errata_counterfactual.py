"""Robustness: occupation-level effect of applying errata E2+E4 inside history.

E2 raises the news-test-2014 En-De frontier in 2018 by ln(29.11)-ln(28.4)=0.0247,
shifting the translation application mean by 0.0247/7 = 0.00353 (5.0% of that
year's mean). E4 raises ARC's 2023 frontier by -ln(0.036)+ln(0.037)=0.0274,
shifting the language-QA application mean by 0.0274/9 = 0.00304 (1.0%). This
script propagates both through the legacy-style occupation panel and reports the
maximal change in cumulative levels relative to the within-year spread.
Result (5 Sep 2026): max 0.5% of a within-year SD; 2023 rank correlation 0.999998.
"""
import importlib.util, sys, re
from pathlib import Path
import pandas as pd

ROOT = Path.home()/"Documents/Workspace/lab-infrastructure/daioe-pipeline"
sys.path.insert(0, str(ROOT/"src"))
spec = importlib.util.spec_from_file_location("bv", ROOT/"mapping/code/build_2024_variants.py")
bv = importlib.util.module_from_spec(spec); spec.loader.exec_module(bv)
from daioe.stage2_ai_progress import _APP_ID
ID_TO_APP = {v:k for k,v in _APP_ID.items()}
VIN = ROOT/"data/vintage/vintage_2025_genailegacy_20260904/out"; bv.OUT = VIN

frames=[]
for f in sorted(VIN.glob("slopes_slimmed_*.parquet")):
    d = pd.read_parquet(f)
    if "application" in d.columns: frames.append(d[["application","year","mean"]])
prog = (pd.concat(frames).drop_duplicates(["application","year"])
        .rename(columns={"mean":"progress"}))
NINE = {ID_TO_APP[i] for i in [2,5,6,7,8,9,10,11,12]}
prog = prog[prog.application.isin(NINE)]

M9 = pd.read_csv(ROOT/"mapping/output/mapping_matrix_9x58_v2018.csv", index_col=0)
M9.columns = M9.columns.astype(int)
apps = pd.read_csv(ROOT/"mapping/raw_data/applications_v2.csv").set_index("ai_app_id")
ab = (pd.read_csv(ROOT/"mapping/raw_data/abilities_v2.csv")
      .drop_duplicates("ability_id").set_index("ability_id")["ability_name"])
rows = {ID_TO_APP[int(apps.loc[aid,"daioe_app_id"])]: M9.loc[aid]
        for aid in apps.index if aid in M9.index and int(apps.loc[aid,"daioe_app_id"]) in [2,5,6,7,8,9,10,11,12]}
M = pd.DataFrame(rows).T
M.columns = [re.sub(r"[^a-z]","",str(ab.get(i,"")).lower()) for i in M9.columns]
M = M.loc[:,[c for c in M.columns if c]]
w52,_ = bv.load_weights(None); social = bv.load_social_score(2.0)

def legacy_panel(z):
    z = z.copy()
    nt = z.groupby("year")["application"].transform("count")
    z["progress"] = z.progress/nt
    return bv.build_panel(M, w52, z, social, 10.0)

base = legacy_panel(prog)
# The slopes 'mean' is already the application mean, so the shift is d/n added directly.
pert2 = prog.copy()
pert2.loc[(pert2.application=="translation") & (pert2.year==2018), "progress"] += 0.00353
pert2.loc[(pert2.application=="reading comprehension") & (pert2.year==2023), "progress"] += 0.00304
var = legacy_panel(pert2)
m = base.merge(var, on=["occ_code_onet","year"], suffixes=("_b","_v"))
m["dcum"] = (m.exp_cumul_v - m.exp_cumul_b).abs()
for y in [2018, 2023, 2025]:
    my = m[m.year==y]
    sd = my.exp_cumul_b.std()
    print(f"year {y}: max |change in cumulative level| = {my.dcum.max():.5f}, "
          f"within-year SD of levels = {sd:.3f}, ratio = {100*my.dcum.max()/sd:.3f}%")
sp = m[m.year==2023].exp_cumul_b.corr(m[m.year==2023].exp_cumul_v, method="spearman")
print(f"2023 rank correlation corrected vs published: {sp:.6f}")
