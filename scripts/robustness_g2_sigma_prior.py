"""Robustness: sensitivity of the second-generation composites to the family priors.

Under the v2 shrinkage rule every application's sigma blends its own history
with its scale-family prior, sigma = (n*own + K*fam)/(n+K), K=5. This script
halves and doubles the FAMILY component only (own histories untouched),
rebuilds the sigmas from the components recorded in g2_sigma_v2.csv, and
recomputes the composites. Result (5 Sep 2026, v2 build): the LEVEL of the 2025
increment remains strongly prior-dependent (factor of roughly 3.5 in either direction,
driven by the four entrants whose sigma is pure prior), while occupation
rankings are essentially unchanged (Spearman >= 0.99). Same conclusion as under
v1: read the 2025 level as provisional, cross-sections as robust.
"""
import importlib.util, sys, re
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
spec = importlib.util.spec_from_file_location("bv", ROOT/"mapping/code/build_2024_variants.py")
bv = importlib.util.module_from_spec(spec); spec.loader.exec_module(bv)
from daioe.stage2_ai_progress import _APP_ID
ID_TO_APP = {v:k for k,v in _APP_ID.items()}
VIN = ROOT/"data/vintage/vintage_2025_genailegacy_20260904/out"; bv.OUT = VIN
GEN4 = {"language modeling","generating images","conversation","generating computer programs from specifications"}

frames=[]
for f in sorted(VIN.glob("slopes_slimmed_*.parquet")):
    d = pd.read_parquet(f)
    if "application" in d.columns: frames.append(d[["application","year","mean"]])
prog = (pd.concat(frames).drop_duplicates(["application","year"])
        .rename(columns={"mean":"progress"}))
prog = prog[prog.application.notna() & (prog.application!="robotics")]

tab = pd.read_csv(ROOT/"data/derived/g2_sigma_v2.csv").drop_duplicates("application").set_index("application")
def sigma_with(fam_mult):
    own = pd.to_numeric(tab["own_sd"], errors="coerce")
    n = tab["n_history_years"].astype(float)
    fam = tab["family_sd"].astype(float)*fam_mult
    K = tab["K"].astype(float)
    s = (n*own.fillna(0) + K*fam)/(n+K)
    return s

apps = pd.read_csv(ROOT/"mapping/raw_data/applications_v2.csv")
M9 = pd.read_csv(ROOT/"mapping/output/mapping_matrix_9x58_v2018.csv", index_col=0)
M9.columns = M9.columns.astype(int)
ab = (pd.read_csv(ROOT/"mapping/raw_data/abilities_v2.csv")
      .drop_duplicates("ability_id").set_index("ability_id")["ability_name"])
name_to_id = {v.strip().lower():k for k,v in ab.items()}
frs = pd.read_excel(ROOT/"mapping/raw_data/mapping_matrix.xlsx", sheet_name="Combined").set_index("abilities")
app_meta = apps.set_index("ai_app_id"); rows={}
for aid in app_meta.index:
    dn = ID_TO_APP[int(app_meta.loc[aid,"daioe_app_id"])]
    if aid in M9.index and int(app_meta.loc[aid,"daioe_app_id"]) in [2,5,6,7,8,9,10,11,12]:
        rows[dn]=M9.loc[aid]
    else:
        f_raw=frs.loc[app_meta.loc[aid,"frs_row"]].drop("ability_id")
        r=pd.Series({name_to_id.get(str(n).strip().lower()):float(v) for n,v in f_raw.items()})
        rows[dn]=r[[i for i in r.index if i is not None and not pd.isna(i)]]
M=pd.DataFrame(rows).T; M.columns=M.columns.astype(int)
M.columns=[re.sub(r"[^a-z]","",str(ab.get(i,"")).lower()) for i in M.columns]
M=M.loc[:,[c for c in M.columns if c]]
w52,_=bv.load_weights(None); social=bv.load_social_score(2.0)

def panel_with(fam_mult, members=None):
    z=prog.copy()
    if members is not None: z=z[z.application.isin(members)]
    z["progress"]=z.progress/z.application.map(sigma_with(fam_mult))
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
        print(f"{label} family-prior x{mult}: Spearman 2025 increment={sp_chg:.4f}, level={sp_cum:.4f}, "
              f"mean 2025 increment {y25.exp_change_b.mean():.3f} -> {y25.exp_change_v.mean():.3f}")
