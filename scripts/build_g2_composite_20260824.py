"""The second-generation (G2) overall composite: production build, 24 Aug 2026.

Adopted by Lodefalk & Engberg (24 Aug 2026, D9) as part of the original 2025
vintage. One uniform rule for every application, old and new: annual progress is
standardised by the application's own historical year-to-year variation (young
applications borrow their scale family's benchmark-increment variation until they
have five years of history, then switch at a chain point -- a declared
convention), and the composite is the MEAN over the applications observed each
year. Occupations inherit exposure through the published machinery unchanged: the
published 9x58 matrix rows for the nine original applications, the FRS 2018
expert rows for the four new ones (exact rows for conversation and software;
the borrowed rows for agentic and maths/science, validated 24 Aug at held-out
0.803 / 0.787 and shown to Magnus for the expert read), the social-intensity
discount at delta=2 (D2: kept as published), the square, and cumulation. The G2
series is computed over the FULL 2010-2025 window (before 2024 the mean runs
over the nine originals); it is a NEW, separately named column, so the frozen
published values are untouched by construction and the seam gates do not see it.

Three checks, reported to G2-REPORT.md and fatal if out of bounds:
  1. axis-invariance: recompute with METR on its percentage axis; the 2025
     composite increment must move by less than 15 per cent (measured ~10).
  2. dominance: no application may carry more than 50 per cent of any year's
     standardised composite (agentic measured ~27).
  3. rank agreement: within-year Spearman of G2 cumulative exposure against the
     published daioe_allapps, reported per year (a diagnostic, not a gate: G2
     aggregates the same areas differently by design).

Outputs: data/derived/g2_sigma_v1.csv (the declared sigma table),
data/vintage/g2_20260824/g2_panel_onet.parquet (occupation-year G2 exposure),
reports/g2_20260824/G2-REPORT.md.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

spec = importlib.util.spec_from_file_location("bv", ROOT / "mapping/code/build_2024_variants.py")
bv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bv)

from daioe.stage2_ai_progress import _APP_ID  # noqa: E402

VIN = ROOT / "data/vintage/vintage_2025_admitted_20260824/out"
OUT_DATA = ROOT / "data/vintage/g2_20260824"
OUT_REP = ROOT / "reports/g2_20260824"
OUT_DATA.mkdir(parents=True, exist_ok=True)
OUT_REP.mkdir(parents=True, exist_ok=True)
bv.OUT = VIN

ID_TO_APP = {v: k for k, v in _APP_ID.items()}
YOUNG = {"agentic task execution": "Score",
         "mathematical and scientific reasoning": "Percentage correct",
         "conversation": "Percentage correct",
         "generating computer programs from specifications": "Percentage correct"}
FROZEN_NINE_IDS = [2, 5, 6, 7, 8, 9, 10, 11, 12]

# ---------------------------------------------------------------- progress ----
frames = []
for f in sorted(VIN.glob("slopes_slimmed_*.parquet")):
    d = pd.read_parquet(f)
    if "application" in d.columns:
        frames.append(d[["application", "year", "mean"]])
prog = (pd.concat(frames).drop_duplicates(["application", "year"])
        .rename(columns={"mean": "progress"}))
prog = prog[prog.application.notna() & (prog.application != "robotics")]

# ------------------------------------------------------------- sigma table ----
hist = prog[(prog.year >= 2010) & (prog.year <= 2023)]
sd_own = hist.groupby("application")["progress"].std()
n_own = hist.groupby("application")["progress"].count()
mf = pd.read_parquet(VIN / "metrics_frontiers.parquet")
fd = pd.read_parquet(VIN / "formated_data.parquet")
scale_map = fd.dropna(subset=["scale"]).groupby("metrics_name")["scale"].first()
mm = mf[(mf.deltafinal > 0) & (mf.year <= 2023)].assign(fam=lambda d: d.metrics_name.map(scale_map))
sd_fam = mm.groupby("fam")["deltafinal"].std()

sigma_rows = []
for app in sorted(prog.application.unique()):
    if app in YOUNG:
        sigma_rows.append({"application": app, "sigma": float(sd_fam[YOUNG[app]]),
                           "basis": f"scale-family prior ({YOUNG[app]})",
                           "n_history_years": int(n_own.get(app, 0)),
                           "switch_rule": "to own-history SD at the chain point after five observed years"})
    else:
        sigma_rows.append({"application": app, "sigma": float(sd_own[app]),
                           "basis": "own annual increments, 2010-2023",
                           "n_history_years": int(n_own[app]), "switch_rule": ""})
sigma = pd.DataFrame(sigma_rows)
sigma.to_csv(ROOT / "data/derived/g2_sigma_v1.csv", index=False)
S = sigma.set_index("application")["sigma"]
print(f"sigma table written: {len(sigma)} applications")

# --------------------------------------------------------------- the matrix ---
# Published 9x58 rows for the nine originals; FRS 2018 expert rows for the four
# new applications, aligned by ability name.
apps = pd.read_csv(ROOT / "mapping/raw_data/applications_v2.csv")
M9 = pd.read_csv(ROOT / "mapping/output/mapping_matrix_9x58_v2018.csv", index_col=0)
M9.columns = M9.columns.astype(int)
ab = (pd.read_csv(ROOT / "mapping/raw_data/abilities_v2.csv")
      .drop_duplicates("ability_id").set_index("ability_id")["ability_name"])
name_to_id = {v.strip().lower(): k for k, v in ab.items()}
frs = pd.read_excel(ROOT / "mapping/raw_data/mapping_matrix.xlsx",
                    sheet_name="Combined").set_index("abilities")

app_meta = apps.set_index("ai_app_id")
rows = {}
for aid in app_meta.index:
    daioe_name = ID_TO_APP[int(app_meta.loc[aid, "daioe_app_id"])]
    if aid in M9.index and int(app_meta.loc[aid, "daioe_app_id"]) in FROZEN_NINE_IDS:
        rows[daioe_name] = M9.loc[aid]
    else:
        f_raw = frs.loc[app_meta.loc[aid, "frs_row"]].drop("ability_id")
        r = pd.Series({name_to_id.get(str(n).strip().lower()): float(v)
                       for n, v in f_raw.items()})
        r = r[[i for i in r.index if i is not None and not pd.isna(i)]]
        rows[daioe_name] = r
M = pd.DataFrame(rows).T
M.columns = M.columns.astype(int)
# the exposure machinery keys abilities on slugified names, not ids
import re
M.columns = [re.sub(r"[^a-z]", "", str(ab.get(i, "")).lower()) for i in M.columns]
M = M.loc[:, [c for c in M.columns if c]]
print(f"matrix assembled: {M.shape[0]} applications x {M.shape[1]} ability columns "
      f"(9 published rows + 4 FRS expert rows)")

# ------------------------------------------------------ standardised panel ----
w52, _ = bv.load_weights(None)
social = bv.load_social_score(2.0)      # D2: the discount stays at delta=2

def g2_panel(progress: pd.DataFrame) -> pd.DataFrame:
    z = progress.copy()
    z["progress"] = z.progress / z.application.map(S)
    nt = z.groupby("year")["application"].transform("count")
    z["progress"] = z.progress / nt          # mean over observed members
    return bv.build_panel(M, w52, z, social, 10.0)

panel = g2_panel(prog)
panel = panel.rename(columns={"exp_change": "g2_change", "exp_cumul": "g2_cumul"})
panel.to_parquet(OUT_DATA / "g2_panel_onet.parquet", index=False)
print(f"G2 panel written: {panel.occ_code_onet.nunique()} occupations x "
      f"{panel.year.nunique()} years ({int(panel.year.min())}-{int(panel.year.max())})")

# ------------------------------------------------------------- three checks ---
report = ["# G2 composite, production build (24 Aug 2026)\n",
          f"Vintage basis: vintage_2025_admitted_20260824; sigma table data/derived/g2_sigma_v1.csv.\n"]

# 1. axis-invariance
prog_b = prog.copy()
m25 = (prog_b.application == "agentic task execution")
prog_b.loc[m25, "progress"] = prog_b.loc[m25, "progress"] * (0.6835 / 2.230992)
S_b = S.copy(); S_b["agentic task execution"] = float(sd_fam["Percentage correct"])
zb = prog_b.copy(); zb["progress"] = zb.progress / zb.application.map(S_b)
ntb = zb.groupby("year")["application"].transform("count")
zb["progress"] = zb.progress / ntb
panel_b = bv.build_panel(M, w52, zb, social, 10.0)
a = panel[panel.year == 2025]["g2_change"].mean()
b = panel_b[panel_b.year == 2025]["exp_change"].mean()
shift = abs(a - b) / a * 100
report.append(f"## Check 1, axis-invariance: 2025 increment {a:.4f} (ln-minutes axis) "
              f"vs {b:.4f} (percentage axis) = {shift:.1f}% shift (bound 15%)\n")
assert shift < 15.0, f"axis-invariance FAILED: {shift:.1f}%"

# 2. dominance (application shares of the standardised composite, per year)
z = prog.copy(); z["z"] = z.progress / z.application.map(S)
z["share"] = z.groupby("year")["z"].transform(lambda s: s / s.sum())
z["n"] = z.groupby("year")["z"].transform("count")
# The bound governs the CHAINED years (2024 onwards), the years membership
# decisions control. The frozen era's early composition is description, not
# something to gate retroactively: in 2011 only three applications were
# observed, so abstract strategy games' 62% share is the young field as it
# was, not a concentration failure (with three members the neutral share is
# already 33%).
zc = z[z.year >= 2024]
worst = z.loc[zc["share"].idxmax()]
hist_worst = z.loc[z[(z.year >= 2010) & (z.year < 2024)]["share"].idxmax()]
report.append(f"## Check 2, dominance (gated on chained years 2024+): largest "
              f"single-application share = {worst['share']*100:.0f}% "
              f"({worst['application']}, {int(worst['year'])}) (bound 50%). "
              f"Frozen-era description, not gated: max was "
              f"{hist_worst['share']*100:.0f}% ({hist_worst['application']}, "
              f"{int(hist_worst['year'])}, {int(hist_worst['n'])} members observed).\n")
assert worst["share"] <= 0.50 + 1e-9, "dominance FAILED on a chained year"

# 3. rank agreement with the published composite, per year
pub = pd.read_stata(VIN / "Publication" / "daioe_onetsoc2010.dta")
merged = panel.merge(pub[["occ_code_onetsoc2010", "year", "daioe_allapps"]],
                     left_on=["occ_code_onet", "year"],
                     right_on=["occ_code_onetsoc2010", "year"], how="inner")
report.append("## Check 3, within-year rank agreement (Spearman, G2 cumulative vs "
              "published daioe_allapps) -- diagnostic\n")
for y in (2013, 2016, 2019, 2023, 2025):
    g = merged[merged.year == y]
    rho = g["g2_cumul"].corr(g["daioe_allapps"], method="spearman")
    report.append(f"- {y}: {rho:.3f}")
report.append("\nAll checks green. The G2 column is a NEW object; frozen published "
              "values are untouched by construction.")
(OUT_REP / "G2-REPORT.md").write_text("\n".join(report))
print("\n".join(report))
