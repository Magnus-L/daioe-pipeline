"""What the agentic subdomain and ai_all look like if the plan is completed.

The plan = agentic gets its exposure column from the v2 (Claude 13-app) matrix and enters the
composite, which is the matrix-decision half that the 18 Aug series switch deliberately did not
take. This reuses mapping/code/build_2024_variants.py's own Eq2/Eq3 machinery rather than
reimplementing it, with OUT pointed at the METR vintage.

Three id systems exist here and they do not agree; the crosswalk is applications_v2.csv's
daioe_app_id column, used explicitly rather than inferred:
    FRS18 matrix row ids   1-16   ("solving real-world technical problems" = 15)
    v2 matrix ai_app_id    1-13   (agentic = 10)
    DAIOE application id          (agentic = 13)
"""
import sys, importlib.util
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path("/Users/mslk/Documents/Workspace/lab-infrastructure/daioe-pipeline")
VINTAGE = ROOT / "data/vintage/vintage_2025_metr_20260818/out"
sys.path.insert(0, str(ROOT / "src"))

spec = importlib.util.spec_from_file_location("bv", ROOT / "mapping/code/build_2024_variants.py")
bv = importlib.util.module_from_spec(spec); spec.loader.exec_module(bv)
bv.OUT = VINTAGE                      # read the METR vintage, not data/out

from daioe.stage2_ai_progress import _APP_ID
ID_TO_APP = {v: k for k, v in _APP_ID.items()}

# ---- progress for every application present in the vintage -------------------------------
frames = []
for f in sorted(VINTAGE.glob("slopes_slimmed_*.parquet")):
    d = pd.read_parquet(f)
    if "application" in d.columns:
        frames.append(d[["application", "year", "mean"]])
prog = (pd.concat(frames).drop_duplicates(["application", "year"])
        .rename(columns={"mean": "progress"}))
prog = prog[prog.application.notna() & (prog.application != "robotics")]

# ---- the v2 matrix, indexed by DAIOE application name -------------------------------------
apps = pd.read_csv(ROOT / "mapping/raw_data/applications_v2.csv")
M13 = bv.matrix_claude(apps, ROOT / "mapping/output/mapping_matrix_claude_v2026_13apps.csv")
# matrix_claude indexes by frs_row; relabel to the DAIOE application name via daioe_app_id
frs_to_daioe = {r.frs_row.strip().lower(): ID_TO_APP[int(r.daioe_app_id)] for r in apps.itertuples()}
M13.index = [frs_to_daioe[i] for i in M13.index]

NINE = sorted(set(prog.application) & set(M13.index) & {ID_TO_APP[i] for i in [2,5,6,7,8,9,10,11,12]})
THIRTEEN = sorted(set(prog.application) & set(M13.index))
print("nine-app composition :", len(NINE))
print("full composition     :", len(THIRTEEN), "->", sorted(set(THIRTEEN) - set(NINE)))

w52, w58 = bv.load_weights(None)
social = bv.load_social_score(2.0)

def panel(apps_keep, use58=False, social_on=True):
    M = M13.loc[[a for a in M13.index if a in apps_keep]]
    return bv.build_panel(M, w58 if use58 else w52, prog[prog.application.isin(apps_keep)],
                          social if social_on else None, 10.0)

p9   = panel(NINE)
p9ag = panel(NINE + ["agentic task execution"])
p13  = panel(THIRTEEN)
pAg  = panel(["agentic task execution"])

# ---- 1. the agentic subdomain on its own ---------------------------------------------------
print("\n" + "="*78)
print("1. THE AGENTIC SUBDOMAIN: its own exposure panel (2025, the only year it moves)")
print("="*78)
a25 = pAg[pAg.year == 2025].set_index("occ_code_onet")["exp_change"]
print(f"occupations: {len(a25)}   mean {a25.mean():.4f}   sd {a25.std():.4f}   "
      f"min {a25.min():.4f}   max {a25.max():.4f}")

# ---- 2. ai_all with and without ------------------------------------------------------------
print("\n" + "="*78)
print("2. ai_all (allapps): nine applications vs the full thirteen")
print("="*78)
for y in [2023, 2024, 2025]:
    a = p9[p9.year == y].set_index("occ_code_onet")["exp_cumul"]
    b = p13[p13.year == y].set_index("occ_code_onet")["exp_cumul"]
    j = pd.concat([a, b], axis=1, keys=["nine", "full"]).dropna()
    if j.empty: continue
    rho = j.nine.corr(j.full, method="spearman")
    print(f"  {y}: cumulative mean {j.nine.mean():9.3f} -> {j.full.mean():9.3f} "
          f"({j.full.mean()/j.nine.mean():.2f}x)   Spearman {rho:.4f}")

a = p9[p9.year == 2025].set_index("occ_code_onet")["exp_change"]
b = p13[p13.year == 2025].set_index("occ_code_onet")["exp_change"]
print(f"\n  2025 INCREMENT alone: mean {a.mean():.4f} -> {b.mean():.4f} "
      f"({b.mean()/a.mean():.1f}x)")

# ---- 3. who moves --------------------------------------------------------------------------
onet = pd.read_parquet(VINTAGE / "onet_abilities_weighted.parquet")[["occ_code_onet"]].drop_duplicates()
try:
    ttl = pd.read_excel(ROOT / "data/raw/soc_2010_definitions - fixed for Stata.xls")
    ttl.columns = [str(c).strip() for c in ttl.columns]
    code_c = [c for c in ttl.columns if "code" in c.lower()][0]
    title_c = [c for c in ttl.columns if "title" in c.lower()][0]
    base = dict(zip(ttl[code_c].astype(str).str.strip(), ttl[title_c]))
    names = {}
    for k in list(a.index):
        names[k] = base.get(str(k)[:7], str(k))
except Exception as e:
    names = {}
    print("\n(no O*NET titles:", e, ")")

j = pd.concat([a.rename("nine"), b.rename("full")], axis=1).dropna()
j["pshift"] = j.full.rank(pct=True) - j.nine.rank(pct=True)
j["title"] = [names.get(i, i) for i in j.index]
print("\n" + "="*78)
print("3. WHO MOVES: largest percentile gains in the 2025 increment when agentic enters")
print("="*78)
print(j.sort_values("pshift", ascending=False).head(12)[["title", "nine", "full", "pshift"]]
      .to_string(float_format=lambda x: f"{x:8.4f}"))
print("\nlargest losses:")
print(j.sort_values("pshift").head(8)[["title", "nine", "full", "pshift"]]
      .to_string(float_format=lambda x: f"{x:8.4f}"))
ms = j["pshift"].abs().mean()*100
print(f"\nmean |percentile shift| = {ms:.2f} pts; "
      f"Spearman(nine, full) on the 2025 increment = {j.nine.corr(j.full, method='spearman'):.4f}")


# ---- 4. decomposition: which of the four new subdomains does the work -----------------------
print("\n" + "="*78)
print("4. DECOMPOSITION of the 2025 increment (mean over 966 occupations)")
print("="*78)
base = p9[p9.year == 2025]["exp_change"].mean()
rows = [("nine applications (as published)", base)]
for extra in ["agentic task execution", "conversation",
              "generating computer programs from specifications",
              "mathematical and scientific reasoning"]:
    v = panel(NINE + [extra])
    rows.append((f"  + {extra}", v[v.year == 2025]["exp_change"].mean()))
rows.append(("all thirteen (as planned)", p13[p13.year == 2025]["exp_change"].mean()))
for lab, v in rows:
    print(f"  {lab:<52} {v:9.4f}")
print("\n  NB exp_change is squared before scaling, so contributions are not additive.")

# ---- 5. face validity of the agentic exposure column ---------------------------------------
print("\n" + "="*78)
print("5. FACE VALIDITY: most and least agentic-exposed occupations (agentic panel alone)")
print("="*78)
ag = pAg[pAg.year == 2025].set_index("occ_code_onet")["exp_change"].sort_values(ascending=False)
lbl = lambda idx: [names.get(i, str(i)) for i in idx]
top = ag.head(15); bot = ag.tail(10)
print("MOST exposed:")
for i, v in top.items():
    print(f"   {v:8.3f}  {names.get(i, i)}")
print("LEAST exposed:")
for i, v in bot.items():
    print(f"   {v:8.3f}  {names.get(i, i)}")

# does the physical contamination in the FRS row show up at occupation level?
phys = pd.read_parquet(VINTAGE / "onet_social_skills_physical_abilities.parquet")
if "physical_abilities" in phys.columns:
    ph = phys.set_index("occ_code_onet")["physical_abilities"]
    j2 = pd.concat([ag.rename("agentic"), ph], axis=1).dropna()
    print(f"\ncorr(agentic exposure, physical_abilities) = "
          f"{j2.agentic.corr(j2.physical_abilities):.4f} "
          f"(Spearman {j2.agentic.corr(j2.physical_abilities, method='spearman'):.4f})")
    # and against the software application, which has a clean (0.00 physical) FRS row
    sw = panel(["generating computer programs from specifications"])
    sw = sw[sw.year == 2025].set_index("occ_code_onet")["exp_change"]
    j3 = pd.concat([sw.rename("software"), ph], axis=1).dropna()
    print(f"corr(software exposure, physical_abilities) = "
          f"{j3.software.corr(j3.physical_abilities):.4f} "
          f"(Spearman {j3.software.corr(j3.physical_abilities, method='spearman'):.4f})")
    print(f"corr(agentic, software) exposure          = {pd.concat([ag, sw], axis=1).dropna().corr().iloc[0,1]:.4f}")
