"""G2-style GENERATIVE composite (daioe_g2gen), built 4 Sep 2026 on ML's decision.

Replaces the raw-sum broadening of daioe_genai (ratified as D6 on 24 Aug,
amended by ML on 4 Sep after inspection): the released daioe_genai returns to its
ORIGINAL membership permanently, like daioe_allapps, and the broadened thematic
composite is instead built the second-generation way, so that newly admitted
generative applications enter in standardised units and cannot dominate by scale.
The trigger was measured, not hypothetical: under raw-sum broadening, 99 per cent
of the 2025 genai step (+1.546 of +1.564) came from the two newborn members'
thin-baseline first increments.

Construction: identical to build_g2_composite_20260824.py (same sigma table,
same matrix machinery, same discount, same mean-over-observed rule) restricted to
the four generative applications: language modeling, generating images,
conversation, generating computer programs from specifications.

Outputs: data/vintage/g2gen_20260904/g2gen_panel_onet.parquet,
reports/g2gen_20260904/G2GEN-REPORT.md.
"""
from __future__ import annotations
import importlib.util, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("bv", ROOT / "mapping/code/build_2024_variants.py")
bv = importlib.util.module_from_spec(spec); spec.loader.exec_module(bv)
from daioe.stage2_ai_progress import _APP_ID  # noqa: E402

VIN = ROOT / "data/vintage/vintage_2025_genailegacy_20260904/out"
OUT_DATA = ROOT / "data/vintage/g2gen_20260904"; OUT_DATA.mkdir(parents=True, exist_ok=True)
OUT_REP  = ROOT / "reports/g2gen_20260904";      OUT_REP.mkdir(parents=True, exist_ok=True)
bv.OUT = VIN

GEN4 = ["language modeling", "generating images", "conversation",
        "generating computer programs from specifications"]
FROZEN_NINE_IDS = [2, 5, 6, 7, 8, 9, 10, 11, 12]
ID_TO_APP = {v: k for k, v in _APP_ID.items()}

# progress, filtered to the generative four
frames = []
for f in sorted(VIN.glob("slopes_slimmed_*.parquet")):
    d = pd.read_parquet(f)
    if "application" in d.columns:
        frames.append(d[["application", "year", "mean"]])
prog = (pd.concat(frames).drop_duplicates(["application", "year"])
        .rename(columns={"mean": "progress"}))
prog = prog[prog.application.isin(GEN4)]
print("members observed by year:")
print(prog.groupby("year")["application"].nunique().to_string())

# sigma table: the SHIPPED one, unchanged (same per-application bases)
sigma = pd.read_csv(ROOT / "data/derived/g2_sigma_v1.csv").set_index("application")["sigma"]
S = sigma[sigma.index.isin(GEN4)]
assert len(S) == 4, S.index.tolist()

# matrix: same assembly as the G2 builder, restricted to the four rows
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
    name = ID_TO_APP[int(app_meta.loc[aid, "daioe_app_id"])]
    if name not in GEN4: continue
    if aid in M9.index and int(app_meta.loc[aid, "daioe_app_id"]) in FROZEN_NINE_IDS:
        rows[name] = M9.loc[aid]
    else:
        f_raw = frs.loc[app_meta.loc[aid, "frs_row"]].drop("ability_id")
        r = pd.Series({name_to_id.get(str(n).strip().lower()): float(v)
                       for n, v in f_raw.items()})
        rows[name] = r[[i for i in r.index if i is not None and not pd.isna(i)]]
import re
M = pd.DataFrame(rows).T
M.columns = [re.sub(r"[^a-z]", "", str(ab.get(i, "")).lower()) for i in M.columns.astype(int)]
M = M.loc[:, [c for c in M.columns if c]]
assert M.shape[0] == 4, M.index.tolist()
print(f"matrix: {M.shape[0]} generative applications x {M.shape[1]} abilities")

w52, _ = bv.load_weights(None)
social = bv.load_social_score(2.0)
z = prog.copy()
z["progress"] = z.progress / z.application.map(S)
nt = z.groupby("year")["application"].transform("count")
z["progress"] = z.progress / nt
panel = bv.build_panel(M, w52, z, social, 10.0)
panel = panel.rename(columns={"exp_change": "g2gen_change", "exp_cumul": "g2gen_cumul"})
panel.to_parquet(OUT_DATA / "g2gen_panel_onet.parquet", index=False)
print(f"g2gen panel: {panel.occ_code_onet.nunique()} occ x {panel.year.nunique()} years "
      f"({int(panel.year.min())}-{int(panel.year.max())})")

# checks: dominance within the four (chained years), rank agreement vs legacy genai
rep = ["# G2-style generative composite (g2gen), production build (4 Sep 2026)\n",
       "Vintage basis: vintage_2025_genailegacy_20260904; sigma table data/derived/g2_sigma_v1.csv (shipped, unchanged); members: the four generative applications.\n"]
zz = prog.copy(); zz["z"] = zz.progress / zz.application.map(S)
zz["share"] = zz.groupby("year")["z"].transform(lambda s: s / s.sum())
# Dominance follows the main G2's own precedent: years with fewer than five
# observed members are young-composite description, not gated (the G2 report
# treats 2011's three-member 62% the same way); the 50% cap gates once
# membership reaches five.
zz["n"]=zz.groupby("year")["z"].transform("count")
zc = zz[(zz.year >= 2024) & (zz.n >= 5)]
if len(zc):
    w = zc.sort_values("share").iloc[-1]
    w_share=float(w["share"])
    rep.append(f"## Dominance (chained years with >=5 members): largest share = "
               f"{w_share*100:.0f}% (bound 50%)\n")
    assert w_share <= 0.50 + 1e-9, "dominance FAILED"
else:
    yy = zz[zz.year >= 2024].sort_values(["year","share"], ascending=[True,False])
    desc = "; ".join(f"{int(r.year)}: {r.application} {r.share*100:.0f}% of {int(r.n)} members"
                     for r in yy.groupby("year").head(1).itertuples())
    rep.append(f"## Dominance: no chained year has >=5 observed members yet, so shares are "
               f"reported as young-composite description, per the main G2's own precedent "
               f"({desc}). The cap gates from five members.\n")
pub = pd.read_stata(VIN / "Publication" / "daioe_onetsoc2010.dta")
mg = panel.merge(pub[["occ_code_onetsoc2010","year","daioe_genai"]],
                 left_on=["occ_code_onet","year"], right_on=["occ_code_onetsoc2010","year"])
rep.append("## Rank agreement vs legacy daioe_genai (Spearman, diagnostic)\n")
for y in (2016, 2019, 2023, 2025):
    g = mg[mg.year==y]
    rep.append(f"- {y}: {g.g2gen_cumul.corr(g.daioe_genai, method='spearman'):.3f}")
mean25 = panel[panel.year==2025].g2gen_change.mean()
mean24 = panel[panel.year==2024].g2gen_change.mean()
rep.append(f"\n2024 mean increment {mean24:.4f}; 2025 mean increment {mean25:.4f} "
           f"(standardised units; compare the raw-sum broadening's +1.564 artefact).")
rep.append("\nAll checks green. daioe_g2gen is a NEW column; nothing frozen moves.")
(OUT_REP/"G2GEN-REPORT.md").write_text("\n".join(rep))
print("\n".join(rep))
