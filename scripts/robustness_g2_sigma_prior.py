"""Robustness: sensitivity of the second-generation composites to the borrowed sigmas.

Halves and doubles the scale-family standard deviations that the four young
applications borrow, and rebuilds the g2 panels. Result (5 Sep 2026): the LEVEL
of the 2025 increment moves by a factor of roughly 3 in either direction, while
occupation rankings are essentially unchanged (Spearman >= 0.995 for both
increments and levels, g2all and g2gen alike). The size of the 2025 step is
prior-dependent; the cross-section of occupations is not.
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
VIN = ROOT/"data/vintage/vintage_2025_genailegacy_20260904/out"
bv.OUT = VIN
YOUNG = {"agentic task execution","mathematical and scientific reasoning",
         "conversation","generating computer programs from specifications"}
GEN4 = {"language modeling","generating images","conversation",
        "generating computer programs from specifications"}

frames=[]
for f in sorted(VIN.glob("slopes_slimmed_*.parquet")):
    d = pd.read_parquet(f)
    if "application" in d.columns:
        frames.append(d[["application","year","mean"]])
prog = (pd.concat(frames).drop_duplicates(["application","year"])
        .rename(columns={"mean":"progress"}))
prog = prog[prog.application.notna() & (prog.application!="robotics")]

S = pd.read_csv(ROOT/"data/derived/g2_sigma_v1.csv").set_index("application")["sigma"]

apps = pd.read_csv(ROOT/"mapping/raw_data/applications_v2.csv")
M9 = pd.read_csv(ROOT/"mapping/output/mapping_matrix_9x58_v2018.csv", index_col=0)
M9.columns = M9.columns.astype(int)
ab = (pd.read_csv(ROOT/"mapping/raw_data/abilities_v2.csv")
      .drop_duplicates("ability_id").set_index("ability_id")["ability_name"])
name_to_id = {v.strip().lower():k for k,v in ab.items()}
frs = pd.read_excel(ROOT/"mapping/raw_data/mapping_matrix.xlsx", sheet_name="Combined").set_index("abilities")
FROZEN_NINE_IDS=[2,5,6,7,8,9,10,11,12]
app_meta = apps.set_index("ai_app_id"); rows={}
for aid in app_meta.index:
    dn = ID_TO_APP[int(app_meta.loc[aid,"daioe_app_id"])]
    if aid in M9.index and int(app_meta.loc[aid,"daioe_app_id"]) in FROZEN_NINE_IDS:
        rows[dn]=M9.loc[aid]
    else:
        f_raw=frs.loc[app_meta.loc[aid,"frs_row"]].drop("ability_id")
        r=pd.Series({name_to_id.get(str(n).strip().lower()):float(v) for n,v in f_raw.items()})
        rows[dn]=r[[i for i in r.index if i is not None and not pd.isna(i)]]
M=pd.DataFrame(rows).T; M.columns=M.columns.astype(int)
M.columns=[re.sub(r"[^a-z]","",str(ab.get(i,"")).lower()) for i in M.columns]
M=M.loc[:,[c for c in M.columns if c]]
w52,_=bv.load_weights(None); social=bv.load_social_score(2.0)

def panel_with(mult, members=None):
    z=prog.copy()
    if members is not None: z=z[z.application.isin(members)]
    sig=S.copy()
    for a in YOUNG:
        if a in sig.index: sig[a]=sig[a]*mult
    z["progress"]=z.progress/z.application.map(sig)
    nt=z.groupby("year")["application"].transform("count")
    z["progress"]=z.progress/nt
    mm = M if members is None else M.loc[[a for a in M.index if a in members]]
    return bv.build_panel(mm, w52, z, social, 10.0)

for label, members in [("g2all", None), ("g2gen", GEN4)]:
    base=panel_with(1.0, members)
    for mult in (2.0, 0.5):
        var=panel_with(mult, members)
        m=base.merge(var, on=["occ_code_onet","year"], suffixes=("_b","_v"))
        y25=m[m.year==2025]
        sp_chg=y25.exp_change_b.corr(y25.exp_change_v, method="spearman")
        sp_cum=y25.exp_cumul_b.corr(y25.exp_cumul_v, method="spearman")
        print(f"{label} prior-sigma x{mult}: Spearman 2025 increment={sp_chg:.4f}, 2025 level={sp_cum:.4f}, "
              f"mean 2025 increment {y25.exp_change_b.mean():.3f} -> {y25.exp_change_v.mean():.3f}")
