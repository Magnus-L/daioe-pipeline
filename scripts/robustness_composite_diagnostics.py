"""Robustness: composite diagnostics reported in DOCUMENTATION.md and VINTAGES.md.

One script, six checks (results of 5 Sep 2026 in parentheses):
  A. Squared vs unsquared construction, legacy nine applications: within-year
     increment rankings identical by construction (Spearman 1.000); cumulative
     level rankings 0.97-1.00 in every year.
  B. 2025 application-level mean increment of the second-generation composites
     with and without the four first-measured-year entrants (g2all 1.15 vs 0.59;
     g2gen 1.26 vs 0.75, sigma v2) - the honest range for the 2025 step.
  E. Leave-one-out member influence, g2all 2025 (largest under sigma v2: maths/science and software engineering).
  G. Time-series agreement of the two overall composites: occupation-mean annual
     increment correlation 0.81 over 2013-2023, 0.30 through 2025 (sigma v2).
  H. Expert-row swap bound for the two new columns (Spearman 0.996).
  I. Frozen-window peak cell per taxonomy (2023 clerical occupations).
"""
import importlib.util, sys, re
from pathlib import Path
import numpy as np, pandas as pd

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
prog = prog[prog.application.notna() & (prog.application!="robotics")]
S = pd.read_csv(ROOT/"data/derived/g2_sigma_v2.csv").drop_duplicates("application").set_index("application")["sigma"]

# matrix machinery (as in the g2 build)
apps = pd.read_csv(ROOT/"mapping/raw_data/applications_v2.csv").set_index("ai_app_id")
M9 = pd.read_csv(ROOT/"mapping/output/mapping_matrix_9x58_v2018.csv", index_col=0); M9.columns=M9.columns.astype(int)
ab = pd.read_csv(ROOT/"mapping/raw_data/abilities_v2.csv").drop_duplicates("ability_id").set_index("ability_id")["ability_name"]
name_to_id = {v.strip().lower():k for k,v in ab.items()}
frs = pd.read_excel(ROOT/"mapping/raw_data/mapping_matrix.xlsx", sheet_name="Combined").set_index("abilities")
FROZEN=[2,5,6,7,8,9,10,11,12]; rows={}; frs_rows={}
for aid in apps.index:
    dn = ID_TO_APP[int(apps.loc[aid,"daioe_app_id"])]
    if aid in M9.index and int(apps.loc[aid,"daioe_app_id"]) in FROZEN:
        rows[dn]=M9.loc[aid]
    else:
        f_raw=frs.loc[apps.loc[aid,"frs_row"]].drop("ability_id")
        r=pd.Series({name_to_id.get(str(n).strip().lower()):float(v) for n,v in f_raw.items()})
        rows[dn]=r[[i for i in r.index if i is not None and not pd.isna(i)]]
        frs_rows[dn]=apps.loc[aid,"frs_row"]
M=pd.DataFrame(rows).T; M.columns=[re.sub(r"[^a-z]","",str(ab.get(i,"")).lower()) for i in pd.Index(M.columns).astype(int)]
M=M.loc[:,[c for c in M.columns if c]]
w52,_=bv.load_weights(None); social=bv.load_social_score(2.0)
NINE={ID_TO_APP[i] for i in FROZEN}

def panel(z, members=None, square=True):
    z=z.copy()
    if members is not None: z=z[z.application.isin(members)]
    mm=M.loc[[a for a in M.index if members is None or a in members]]
    # inline replica of bv.build_panel with a square toggle
    abil=[c for c in mm.columns if c in w52.columns]; Mx=mm[abil]; Wx=w52[abil]
    out=[]
    for year,g in z.groupby("year"):
        p=g.set_index("application").progress
        a=[x for x in Mx.index if x in p.index]
        if not a: continue
        ai=Mx.loc[a].mul(p.loc[a],axis=0).sum(axis=0)
        ec=Wx.values@ai.reindex(abil).fillna(0.0).values
        out.append(pd.DataFrame({"occ":Wx.index,"year":year,"chg":ec}))
    pl=pd.concat(out,ignore_index=True)
    pl["chg"]*=pl.occ.map(social).values
    pl["chg"]=(pl.chg**2 if square else pl.chg)*10.0
    pl=pl.sort_values(["occ","year"])
    pl["cum"]=pl.groupby("occ").chg.cumsum()
    return pl

print("== A. squared vs unsquared (legacy nine, raw progress) ==")
zn=prog[prog.application.isin(NINE)]
sq=panel(zn); un=panel(zn,square=False)
m=sq.merge(un,on=["occ","year"],suffixes=("_sq","_un"))
for y in (2015,2020,2023,2025):
    my=m[m.year==y]
    print(f"  {y}: Spearman levels={my.cum_sq.corr(my.cum_un,method='spearman'):.4f}  increments={my.chg_sq.corr(my.chg_un,method='spearman'):.4f}")

print("== B/D. g2 2025 means, full vs excluding first-measured-year entrants (application level) ==")
std=prog.copy(); std["z"]=std.progress/std.application.map(S)
o25=std[std.year==2025].set_index("application").z
young={"agentic task execution","mathematical and scientific reasoning","conversation","generating computer programs from specifications"}
GEN4={"language modeling","generating images","conversation","generating computer programs from specifications"}
print(f"  g2all 2025: all observed mean={o25.mean():.3f}; excl. entrants={o25[~o25.index.isin(young)].mean():.3f}")
g=o25[o25.index.isin(GEN4)]
print(f"  g2gen 2025: all observed mean={g.mean():.3f}; excl. entrants={g[~g.index.isin(young)].mean():.3f}")

print("== E. leave-one-out, g2all 2025 (application level) ==")
for a in o25.index:
    print(f"  drop {a[:40]:42s} mean={o25.drop(a).mean():.3f}")

print("== G. time-series agreement allapps vs g2all, occupation-mean annual increments ==")
pan=pd.read_stata(ROOT/"data/vintage/vintage_2025_v110rc3_20260905/out/Publication/daioe_onetsoc2010.dta")
lv=pan.groupby("year")[["daioe_allapps","daioe_g2all"]].mean()
inc=lv.diff().dropna()
w=inc.loc[2013:2023]
print(f"  corr of annual increments 2013-2023: {w.daioe_allapps.corr(w.daioe_g2all):.3f}; 2013-2025: {inc.loc[2013:2025].daioe_allapps.corr(inc.loc[2013:2025].daioe_g2all):.3f}")

print("== H. FRS row-swap bound for the two new columns ==")
ag="agentic task execution"; ms="mathematical and scientific reasoning"
for a,b in [(ag,ms),(ms,ag)]:
    z=prog[prog.application==a]
    own=panel(z,members={a})
    Msw=M.copy(); Msw.loc[a]=M.loc[b]
    abil=[c for c in Msw.columns if c in w52.columns]
    p25=z[z.year==2025].set_index("application").progress
    ai=Msw.loc[[a],abil].mul(p25.loc[[a]],axis=0).sum(axis=0)
    ec=w52[abil].values@ai.values
    swapped=pd.Series((ec*w52.index.map(social).values)**2, index=w52.index)
    o=own[own.year==2025].set_index("occ").chg
    print(f"  {a[:28]} vs other row: Spearman 2025 increment={o.corr(swapped.reindex(o.index),method='spearman'):.4f}")

print("== I. frozen-window peak cell per taxonomy (daioe_allapps) ==")
for tx in ["onetsoc2010","soc2010","isco08","ssyk2012","ssyk96"]:
    d=pd.read_stata(ROOT/f"data/vintage/vintage_2025_v110rc3_20260905/out/Publication/daioe_{tx}.dta")
    fz=d[(d.year>=2010)&(d.year<=2023)]
    i=fz.daioe_allapps.idxmax(); r=fz.loc[i]
    key=[c for c in d.columns if c not in ("year",) and not c.startswith(("daioe","pctl"))][0]
    print(f"  {tx:12s} peak={r.daioe_allapps:.3f} at {r[key]} in {int(r.year)}")

print("== J. equal vs FRS-mass application weights (g2all) ==")
mass = M.sum(axis=1)
def panel_mass(z0):
    z = z0.copy(); z["progress"] = z.progress/z.application.map(S)
    tot = z.groupby("year")["application"].transform(lambda s: mass.loc[s].sum())
    z["progress"] = z.progress*z.application.map(mass)/tot
    abil=[c for c in M.columns if c in w52.columns]; Mx=M[abil]; Wx=w52[abil]
    out=[]
    for year,g in z.groupby("year"):
        p=g.set_index("application").progress
        a=[x for x in Mx.index if x in p.index]
        ai=Mx.loc[a].mul(p.loc[a],axis=0).sum(axis=0)
        ec=Wx.values@ai.reindex(abil).fillna(0.0).values
        out.append(pd.DataFrame({"occ":Wx.index,"year":year,"chg":ec}))
    pl=pd.concat(out,ignore_index=True)
    pl["chg"]*=pl.occ.map(social).values; pl["chg"]=pl.chg**2*10
    pl=pl.sort_values(["occ","year"]); pl["cum"]=pl.groupby("occ").chg.cumsum()
    return pl
zs=prog.copy(); zs["progress"]=zs.progress/zs.application.map(S)
nt=zs.groupby("year")["application"].transform("count"); zs["progress"]=zs.progress/nt
abil=[c for c in M.columns if c in w52.columns]; Mx=M[abil]; Wx=w52[abil]
out=[]
for year,g in zs.groupby("year"):
    pp=g.set_index("application").progress
    a=[x for x in Mx.index if x in pp.index]
    ai=Mx.loc[a].mul(pp.loc[a],axis=0).sum(axis=0)
    ec=Wx.values@ai.reindex(abil).fillna(0.0).values
    out.append(pd.DataFrame({"occ":Wx.index,"year":year,"chg":ec}))
peq=pd.concat(out,ignore_index=True)
peq["chg"]*=peq.occ.map(social).values; peq["chg"]=peq.chg**2*10
peq=peq.sort_values(["occ","year"]); peq["cum"]=peq.groupby("occ").chg.cumsum()
pms=panel_mass(prog)
mm=peq.merge(pms,on=["occ","year"],suffixes=("_eq","_ms"))
for y in (2023,2025):
    my=mm[mm.year==y]
    print(f"  {y}: Spearman levels={my.cum_eq.corr(my.cum_ms,method='spearman'):.4f} "
          f"increments={my.chg_eq.corr(my.chg_ms,method='spearman'):.4f}")
