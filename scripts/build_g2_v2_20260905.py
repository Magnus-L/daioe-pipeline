"""Second-generation composites, v2 build (5 Sep 2026).

Ordered by ML after the external-review round, three changes against the v1
build (scripts/build_g2_composite_20260824.py), none touching any published or
deposited value (the g2 columns first ship with v1.1.0):

1. SHRINKAGE SIGMAS replace the five-year cliff. Every application's sigma is
   the credibility-weighted blend  sigma_a = (n_a*sd_own_a + K*sd_fam(a)) / (n_a + K),
   with K = 5: the scale-family prior carries the weight of five years of
   pseudo-history, the same information bar the retired cliff demanded before
   trusting own history at all. The blend is continuous in n, so there is no
   unit break at any threshold; as an application's history accumulates, the
   prior's influence decays smoothly. An application's family is the scale
   family carrying the majority of its positive frozen increments. This also
   damps the inverse-volatility reward of pure own-SD standardisation: very
   smooth series are pulled toward their family's typical variation.
2. A BALANCED-BASKET COMPANION, daioe_g2nine: the same construction restricted
   to the nine original applications, so a user can separate capability
   progress from composition change at a glance.
3. A LEAVE-ONE-OUT influence table and member-contribution shares per chained
   year, in the report (OECD/JRC composite-indicator practice).

Outputs: data/derived/g2_sigma_v2.csv, data/vintage/g2v2_20260905/*.parquet,
reports/g2v2_20260905/G2V2-REPORT.md. Checks (fatal): axis-invariance bound
15%; dominance bound one half on chained years.
"""
from __future__ import annotations
import importlib.util, sys, re
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("bv", ROOT / "mapping/code/build_2024_variants.py")
bv = importlib.util.module_from_spec(spec); spec.loader.exec_module(bv)
from daioe.stage2_ai_progress import _APP_ID  # noqa: E402

ID_TO_APP = {v: k for k, v in _APP_ID.items()}
VIN = ROOT / "data/vintage/vintage_2025_genailegacy_20260904/out"
OUT_DATA = ROOT / "data/vintage/g2v2_20260905"; OUT_DATA.mkdir(parents=True, exist_ok=True)
OUT_REP = ROOT / "reports/g2v2_20260905"; OUT_REP.mkdir(parents=True, exist_ok=True)
bv.OUT = VIN
K = 5.0
NINE = {ID_TO_APP[i] for i in [2, 5, 6, 7, 8, 9, 10, 11, 12]}
GEN4 = {"language modeling", "generating images", "conversation",
        "generating computer programs from specifications"}
YOUNG_FAM = {"agentic task execution": "Score",
             "mathematical and scientific reasoning": "Percentage correct",
             "conversation": "Percentage correct",
             "generating computer programs from specifications": "Percentage correct"}

# ---- progress ----------------------------------------------------------------
frames = []
for f in sorted(VIN.glob("slopes_slimmed_*.parquet")):
    d = pd.read_parquet(f)
    if "application" in d.columns:
        frames.append(d[["application", "year", "mean"]])
prog = (pd.concat(frames).drop_duplicates(["application", "year"])
        .rename(columns={"mean": "progress"}))
prog = prog[prog.application.notna() & (prog.application != "robotics")]

# ---- sigma v2 ----------------------------------------------------------------
hist = prog[(prog.year >= 2010) & (prog.year <= 2023)]
sd_own = hist.groupby("application")["progress"].std()
n_own = hist.groupby("application")["progress"].count()
mf = pd.read_parquet(VIN / "metrics_frontiers.parquet")
fd = pd.read_parquet(VIN / "formated_data.parquet")
scale_map = fd.dropna(subset=["scale"]).groupby("metrics_name")["scale"].first()
mm = mf[(mf.deltafinal > 0) & (mf.year <= 2023)].assign(fam=lambda d: d.metrics_name.map(scale_map))
sd_fam = mm.groupby("fam")["deltafinal"].std()
app_of = fd.groupby("metrics_name")["parent_name"].first()
# majority scale family per application, over positive frozen increments
mm2 = mm.assign(app=lambda d: d.metrics_name.map(app_of))
fam_mode = mm2.groupby("app")["fam"].agg(lambda s: s.mode().iloc[0])
PARENT_TO_APP = {"Playing abstract games with extensive hints": "abstract strategy games",
                 "Simple video games": "real-time video games",
                 "Imagenet Image Recognition": "image recognition",
                 "Image classification": "image recognition",
                 "Image comprehension": "visual question answering",
                 "Drawing pictures": "generating images",
                 "Language comprehension and question-answering": "reading comprehension",
                 "Accurate modelling of human language.": "language modeling",
                 "Translation between human langauges": "translation",
                 "Speech Recognition": "speech recognition"}
fam_by_app = {}
for parent, fam in fam_mode.items():
    app = PARENT_TO_APP.get(parent)
    if app:
        fam_by_app.setdefault(app, []).append(fam)
sigma_rows = []
for app in sorted(prog.application.unique()):
    n = float(n_own.get(app, 0) or 0)
    own = float(sd_own.get(app, np.nan))
    if app in YOUNG_FAM:
        fam = YOUNG_FAM[app]
    else:
        fams = fam_by_app.get(app, [])
        fam = pd.Series(fams).mode().iloc[0] if fams else "Percentage correct"
    prior = float(sd_fam[fam])
    if n >= 1 and np.isfinite(own):
        sig = (n * own + K * prior) / (n + K)
        basis = f"shrinkage K={K:.0f}: own SD {own:.4f} (n={n:.0f}) blended with {fam} prior {prior:.4f}"
    else:
        sig = prior
        basis = f"shrinkage K={K:.0f}: no own history, {fam} prior"
    sigma_rows.append({"application": app, "sigma": sig, "basis": basis,
                       "n_history_years": int(n), "family": fam,
                       "own_sd": own if np.isfinite(own) else "",
                       "family_sd": prior, "K": K})
sigma = pd.DataFrame(sigma_rows).drop_duplicates("application")
sigma.to_csv(ROOT / "data/derived/g2_sigma_v2.csv", index=False)
S = sigma.set_index("application")["sigma"]
print(f"sigma v2 written: {len(sigma)} applications (shrinkage K={K:.0f})")

# ---- matrix ------------------------------------------------------------------
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
    dn = ID_TO_APP[int(app_meta.loc[aid, "daioe_app_id"])]
    if aid in M9.index and int(app_meta.loc[aid, "daioe_app_id"]) in [2, 5, 6, 7, 8, 9, 10, 11, 12]:
        rows[dn] = M9.loc[aid]
    else:
        f_raw = frs.loc[app_meta.loc[aid, "frs_row"]].drop("ability_id")
        r = pd.Series({name_to_id.get(str(n).strip().lower()): float(v) for n, v in f_raw.items()})
        rows[dn] = r[[i for i in r.index if i is not None and not pd.isna(i)]]
M = pd.DataFrame(rows).T
M.columns = [re.sub(r"[^a-z]", "", str(ab.get(i, "")).lower()) for i in pd.Index(M.columns).astype(int)]
M = M.loc[:, [c for c in M.columns if c]]
w52, _ = bv.load_weights(None)
social = bv.load_social_score(2.0)

def g2_panel(members=None, sigma_series=None):
    z = prog.copy()
    if members is not None:
        z = z[z.application.isin(members)]
    z["progress"] = z.progress / z.application.map(sigma_series if sigma_series is not None else S)
    nt = z.groupby("year")["application"].transform("count")
    z["progress"] = z.progress / nt
    mm_ = M.loc[[a for a in M.index if members is None or a in members]]
    return bv.build_panel(mm_, w52, z, social, 10.0)

panels = {"g2all": g2_panel(), "g2gen": g2_panel(GEN4), "g2nine": g2_panel(NINE)}
for name, pl in panels.items():
    pl = pl.rename(columns={"exp_change": f"{name}_change", "exp_cumul": f"{name}_cumul"})
    pl.to_parquet(OUT_DATA / f"{name}_panel_onet.parquet", index=False)
    panels[name] = pl
print("panels written: g2all, g2gen, g2nine")

# ---- checks and report -------------------------------------------------------
zstd = prog.copy(); zstd["z"] = zstd.progress / zstd.application.map(S)
rep = [f"# G2 v2 build (5 Sep 2026): shrinkage sigmas K={K:.0f}, balanced companion, influence tables\n",
       "Vintage basis: vintage_2025_genailegacy_20260904; sigma table data/derived/g2_sigma_v2.csv.\n"]

# axis-invariance, the v1 construct exactly: the METR series re-expressed as a
# share of the 960-minute ceiling (raw agentic increment 0.6835 on that axis
# against 2.230992 on ln-minutes), with the agentic sigma re-derived on the
# alternative axis (n=0, so the percentage-correct family prior under shrinkage).
prog_b = prog.copy()
mask = prog_b.application == "agentic task execution"
prog_b.loc[mask, "progress"] = prog_b.loc[mask, "progress"] * (0.6835 / 2.230992)
S_b = S.copy(); S_b["agentic task execution"] = float(sd_fam["Percentage correct"])
zb = prog_b.copy(); zb["progress"] = zb.progress / zb.application.map(S_b)
ntb = zb.groupby("year")["application"].transform("count")
zb["progress"] = zb.progress / ntb
panel_b = bv.build_panel(M, w52, zb, social, 10.0)
a = panels["g2all"][panels["g2all"].year == 2025]["g2all_change"].mean()
b = panel_b[panel_b.year == 2025]["exp_change"].mean()
shift = 100 * abs(a - b) / a
rep.append(f"## Check 1, axis-invariance: 2025 composite increment {a:.4f} (ln-minutes axis) vs {b:.4f} (share axis) = {shift:.1f}% shift (bound 15%)\n")
assert shift < 15, "axis-invariance bound violated"

sh = zstd[zstd.year >= 2024]
dom_lines = []
for yr, g in sh.groupby("year"):
    shares = (g.set_index("application").z / g.z.sum()).sort_values(ascending=False)
    top = shares.index[0]; mx = shares.iloc[0]
    assert mx <= 0.5, f"dominance bound violated in {yr}"
    dom_lines.append(f"{int(yr)}: max {100*mx:.0f}% ({top})")
rep.append("## Check 2, dominance (chained years, bound one half): " + "; ".join(dom_lines) + "\n")

pub = pd.read_stata(ROOT / "data/vintage/vintage_2025_v110rc2_20260904/out/Publication/daioe_onetsoc2010.dta")
key = [c for c in pub.columns if not c.startswith(("daioe", "pctl")) and c != "year"][0]
g2 = panels["g2all"].rename(columns={"occ_code_onet": key})
mrg = pub.merge(g2, on=[key, "year"])
rep.append("## Check 3, within-year rank agreement (g2all v2 cumulative vs published daioe_allapps), diagnostic\n")
for yr in (2013, 2016, 2019, 2023, 2025):
    my = mrg[mrg.year == yr]
    rep.append(f"- {yr}: {my.daioe_allapps.corr(my.g2all_cumul, method='spearman'):.3f}")
gg = panels["g2gen"].rename(columns={"occ_code_onet": key})
mg = pub.merge(gg, on=[key, "year"])
rep.append("\n## Rank agreement vs legacy daioe_genai (Spearman, diagnostic)\n")
for yr in (2016, 2019, 2023, 2025):
    my = mg[mg.year == yr]
    rep.append(f"- {yr}: {my.daioe_genai.corr(my.g2gen_cumul, method='spearman'):.3f}")

rep.append("\n## Member contributions, share of summed standardised progress (chained years)\n")
for yr, g in sh.groupby("year"):
    shares = (g.set_index("application").z / g.z.sum()).sort_values(ascending=False)
    rep.append(f"**{int(yr)}**: " + ", ".join(f"{a} {100*v:.0f}%" for a, v in shares.items() if v > 0.005))

rep.append("\n## Leave-one-out influence, application-level mean standardised increment (chained years)\n")
for yr, g in sh.groupby("year"):
    zz = g.set_index("application").z
    base = zz.mean()
    rep.append(f"**{int(yr)}** (all members {base:.3f}): " +
               ", ".join(f"drop {a}: {zz.drop(a).mean():.3f}" for a in zz.index))

y25 = zstd[zstd.year == 2025].set_index("application").z
young = set(YOUNG_FAM)
rep.append(f"\n## Entrant range, 2025 application-level mean: {y25.mean():.3f} with the four first-measured-year entrants, {y25[~y25.index.isin(young)].mean():.3f} without\n")
rep.append(f"g2gen 2025: {y25[y25.index.isin(GEN4)].mean():.3f} with, {y25[y25.index.isin(GEN4 - young)].mean():.3f} without\n")

(OUT_REP / "G2V2-REPORT.md").write_text("\n".join(rep))
print("report written:", OUT_REP / "G2V2-REPORT.md")
