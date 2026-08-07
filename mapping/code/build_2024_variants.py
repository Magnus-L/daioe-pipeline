"""
build_2024_variants.py — decompose the 2024 vintage change into its two moving parts.

The 2024 vintage changes the mapping matrix *and* how social content is handled, at the same chain
point. Run together they cannot be attributed. Three panels separate them:

    R0   published FRS18 matrix, 52 abilities, social discount ON     (the reference)
    A    new Claude matrix,      52 abilities, social discount ON     (R0 -> A = the matrix change)
    B    new Claude matrix,      58 abilities, social discount OFF    (A -> B = the social change)

R0 also serves as a check on this file: if it does not track the published index, the re-implementation
is wrong and nothing downstream of it means anything.

Construction, mirroring `daioe.stage4_index`
--------------------------------------------
    Eq2   ai_impact[j,t]   = sum_i  M[i,j] * progress[i,t]
    Eq3   exp_change[o,t]  = sum_j  r[o,j] * ai_impact[j,t]
    A,R0  exp_change      *= social_score,  social_score = ((1 - S_o) + delta) / max((1 - S_o) + delta)
          exp_change       = exp_change**2 * scale_up
          exp_cumul        = cumsum over years within occupation

Computed in float64. The production pipeline mirrors Stata's float32 storage at every step because it
must reproduce published values bit-for-bit; here the comparison is between panels built the same way,
so the rounding cancels and the extra machinery would only obscure the code.

The 58-element weight profile
-----------------------------
`element_impact` sums to 1 over 52 abilities per occupation; `skill_impact` sums to 1 over 35 skills,
of which the six social skills are about 21 per cent. Variant B concatenates the 52 abilities with the
six social skills and renormalises to 1, which gives the social block roughly 17 per cent of total
weight, set by O*NET's own within-block shares rather than by us. That share is a construction choice
even so, and `--social-share` overrides it for sensitivity analysis.

Note on scope: progress series exist for nine applications. The three added subdomains have no series
until Track B admits them, so they cannot enter any panel here. This file therefore isolates the
matrix and social changes; adding subdomains is a third axis and remains open.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

MAP = Path(__file__).resolve().parents[1]
ROOT = MAP.parent
OUT = ROOT / "data" / "out"
REPORTS = MAP / "reports" / "variants_2024"
REPORTS.mkdir(parents=True, exist_ok=True)

SOCIAL_IDS = list(range(53, 59))
SOCIAL_SKILL_NAMES = [
    "socialperceptiveness", "coordination", "persuasion",
    "negotiation", "instructing", "serviceorientation",
]


def _canon(s: str) -> str:
    return s.replace(" ", "").replace("-", "").lower()


# ------------------------------- inputs -------------------------------

def load_progress() -> pd.DataFrame:
    """application_progress_score by (clean application name, year)."""
    s = pd.read_parquet(OUT / "slopes_slimmed_allapps.parquet")
    return s[["application", "year", "mean"]].rename(columns={"mean": "progress"})


def load_activity_weights() -> pd.DataFrame:
    """Occupation weights for O*NET's own 4.A.4 'Interacting With Others' work activities.

    Built the same way as `element_impact` for abilities: level x importance, each normalised to its
    own scale maximum so the two count equally, then shares within the block. O*NET scores level
    1-7 and importance 1-5, matching how Engberg and the published pipeline handle both.

    These 17 activities are O*NET's published social branch, not anyone's curation of it, which is
    the point: they give the granularity the six social skills lack (leadership, care, negotiation,
    service, teaching are separate here) while remaining a citation to O*NET.
    """
    d = pd.read_excel(ROOT / "data" / "raw" / "Work_Activities_Onet_Feb2018_22_2.xlsx")
    d.columns = [c.strip() for c in d.columns]
    leaf = d[d["Element ID"].astype(str).str.match(r"^4\.A\.\d+\.[a-z]\.\d+$")]
    wide = leaf.pivot_table(index=["O*NET-SOC Code", "Element ID"], columns="Scale ID",
                            values="Data Value").reset_index()
    wide["v"] = (wide["LV"] / 7.0) * (wide["IM"] / 5.0)
    w = wide.pivot_table(index="O*NET-SOC Code", columns="Element ID", values="v")
    w.index.name = "occ_code_onet"

    # Normalise over EVERY work activity, then keep the social ones. Normalising within the 17
    # would make each occupation's social block sum to 1, and `combine` would then hand every
    # occupation the same 50 per cent social weight, erasing the cross-occupation variation in
    # social intensity that this whole exercise exists to measure. Sharing against the full activity
    # domain is also what `skill_impact` already does for the six social skills, whose block sums to
    # a varying 0.21 rather than to 1.
    w = w.div(w.sum(axis=1), axis=0)
    social = [c for c in w.columns if str(c).startswith("4.A.4.")]
    return w[social]


def load_weights(social_share: float | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Occupation weight profiles: 52-ability (r_oj) and the 58-element extension.

    The 52-ability profile is the production `element_impact`, rebuilt here from the checkpoint
    rather than re-derived, so it is the same object stage 4 consumes.
    """
    ab = pd.read_parquet(OUT / "onet_abilities_weighted.parquet")
    ab = ab.assign(canon=ab.ability.map(_canon))
    w52 = ab.pivot_table(index="occ_code_onet", columns="canon", values="element_impact")

    sk = pd.read_parquet(OUT / "onet_skills_weighted.parquet")
    sk = sk[sk.skill.isin(SOCIAL_SKILL_NAMES)]
    w6 = sk.pivot_table(index="occ_code_onet", columns="skill", values="skill_impact")

    w58 = combine(w52, w6, social_share)
    return w52, w58


def combine(backbone: pd.DataFrame, block: pd.DataFrame, share: float | None) -> pd.DataFrame:
    """Attach a social block to the 52-ability backbone and renormalise to 1.

    The social block is a *slot*, not an addition: the six social skills and the seventeen
    'Interacting With Others' activities are alternative occupants of it, never both. Three of the
    six skills have near-exact activity counterparts (persuasion / selling or influencing,
    negotiation / resolving conflicts, instructing / training and teaching), so using both would
    count the same work twice.

    `share` forces the block to a stated fraction of total weight; None keeps whatever share O*NET's
    own scores imply, which varies by occupation and is the specification we want, since that
    variation is the social intensity the measure is trying to see.
    """
    cols = list(block.columns)
    out = backbone.join(block, how="inner")
    if share is not None:
        cur = out[cols].sum(axis=1)
        rest = out.drop(columns=cols).sum(axis=1)
        factor = (share / (1.0 - share)) * rest / cur.replace(0, np.nan)
        out[cols] = out[cols].mul(factor.fillna(0.0), axis=0)
    return out.div(out.sum(axis=1), axis=0)


def load_social_score(delta: float) -> pd.Series:
    """The discount factor, exactly as stage 4 builds it (panel max, not per-year)."""
    s = pd.read_parquet(OUT / "onet_social_skills_physical_abilities.parquet")
    temp = (1.0 - s["social_skills"]) + delta
    return pd.Series((temp / temp.max()).values, index=s["occ_code_onet"], name="social_score")


def matrix_claude(apps: pd.DataFrame, path: Path) -> pd.DataFrame:
    """Our matrix as (clean application name) x (canonical ability name)."""
    m = pd.read_csv(path, index_col=0)
    m.columns = [int(c) for c in m.columns]
    abil = pd.read_csv(MAP / "raw_data" / "abilities.csv")
    id_to_canon = dict(zip(abil.ability_id, abil.ability_name.map(_canon)))
    m = m.rename(columns=id_to_canon)
    m.index = apps.set_index("ai_app_id").loc[m.index, "frs_row"].str.strip().str.lower()
    return m


def matrix_frs18(applications: list[str]) -> pd.DataFrame:
    """The published FRS18 matrix for the same applications, from the production checkpoint."""
    mm = pd.read_parquet(OUT / "mapping_matrix_long_combined_frs18_frs21.parquet")
    mm = mm[mm.application.isin(applications)]
    return mm.pivot_table(index="application", columns="ability", values="relevance_frs18")


# ------------------------------- construction -------------------------------

def build_panel(M: pd.DataFrame, W: pd.DataFrame, progress: pd.DataFrame,
                social_score: pd.Series | None, scale_up: float) -> pd.DataFrame:
    """Eq2 and Eq3, then discount (optional), square, scale and cumulate."""
    abil = [c for c in M.columns if c in W.columns]
    if not abil:
        raise ValueError("no shared abilities between the matrix and the weight profile")
    M = M[abil]
    W = W[abil]

    rows = []
    for year, g in progress.groupby("year"):
        p = g.set_index("application").progress
        apps = [a for a in M.index if a in p.index]
        if not apps:
            continue
        # Eq2: ability-level AI impact this year.
        ai_impact = M.loc[apps].mul(p.loc[apps], axis=0).sum(axis=0)
        # Eq3: occupation exposure change.
        exp_change = W.values @ ai_impact.reindex(abil).fillna(0.0).values
        rows.append(pd.DataFrame({"occ_code_onet": W.index, "year": year, "exp_change": exp_change}))

    panel = pd.concat(rows, ignore_index=True)
    if social_score is not None:
        panel["exp_change"] *= panel.occ_code_onet.map(social_score).values
    panel["exp_change"] = panel.exp_change ** 2 * scale_up
    panel = panel.sort_values(["occ_code_onet", "year"])
    panel["exp_cumul"] = panel.groupby("occ_code_onet").exp_change.cumsum()
    return panel.reset_index(drop=True)


# ------------------------------- comparison -------------------------------

def compare(panels: dict[str, pd.DataFrame], published: pd.Series | None) -> dict:
    """Cross-occupation rank agreement, which is where this measure's content lives."""
    final = {k: v[v.year == v.year.max()].set_index("occ_code_onet").exp_cumul for k, v in panels.items()}
    keys = list(final)
    out: dict = {"final_year_rank_agreement": {}, "by_year_rank_agreement": {}}

    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            j = pd.concat([final[a], final[b]], axis=1, keys=["a", "b"]).dropna()
            out["final_year_rank_agreement"][f"{a} vs {b}"] = round(float(j.a.corr(j.b, method="spearman")), 4)

    if published is not None:
        for k, s in final.items():
            j = pd.concat([s, published], axis=1, keys=["ours", "pub"]).dropna()
            out["final_year_rank_agreement"][f"{k} vs published"] = round(float(j.ours.corr(j.pub, method="spearman")), 4)

    years = sorted(set(panels[keys[0]].year))
    for y in years:
        cur = {k: v[v.year == y].set_index("occ_code_onet").exp_cumul for k, v in panels.items()}
        j = pd.concat([cur["A"], cur["B"]], axis=1, keys=["A", "B"]).dropna()
        out["by_year_rank_agreement"][int(y)] = round(float(j.A.corr(j.B, method="spearman")), 4)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--matrix", default=str(MAP / "output" / "mapping_matrix_claude_v2026.csv"))
    ap.add_argument("--apps", default=str(MAP / "raw_data" / "applications_v2.csv"))
    ap.add_argument("--delta", type=float, default=2.0, help="social_weight from config.yaml")
    ap.add_argument("--scale-up", type=float, default=10.0)
    ap.add_argument("--social-share", type=float, default=None,
                    help="force the social block to this share of total weight in variant B")
    args = ap.parse_args()

    apps = pd.read_csv(args.apps)
    progress = load_progress()
    w52, w58 = load_weights(args.social_share)
    social_score = load_social_score(args.delta)

    M_new = matrix_claude(apps, Path(args.matrix))
    scored = sorted(set(progress.application) & set(M_new.index))
    M_frs = matrix_frs18(scored)

    # A2 splits what an A -> B contrast otherwise confounds. Going from A to B changes two things
    # at once: the six social abilities enter the mapping matrix, AND the occupation-level discount
    # comes off. Magnus's earlier prototype varied only the second (and with a different discount
    # rule), which is why it saw agreement of 0.971 where this file first reported 0.913. With A2
    # in between, A -> A2 is the cost of admitting social abilities and A2 -> B is the cost of
    # retiring the discount, and the two can be told apart.
    panels = {
        "R0": build_panel(M_frs, w52, progress, social_score, args.scale_up),
        "A":  build_panel(M_new, w52, progress, social_score, args.scale_up),
        "A2": build_panel(M_new, w58, progress, social_score, args.scale_up),
        "B":  build_panel(M_new, w58, progress, None, args.scale_up),
    }
    for k, v in panels.items():
        v.to_csv(REPORTS / f"panel_{k}.csv", index=False)

    pub = pd.read_csv(MAP / "raw_data" / "daioe_onetsoc2010.csv", sep=None, engine="python")
    pub = pub[pub.year == pub.year.max()].set_index("occ_code_onetsoc2010")["daioe_allapps"]

    result = {
        "applications_scored": scored,
        "note": "the three added subdomains have no progress series yet and are absent from every panel",
        "social_block_share_in_B": round(float(w58[SOCIAL_SKILL_NAMES].sum(axis=1).mean()), 4),
        "delta": args.delta, "scale_up": args.scale_up,
        **compare(panels, pub),
    }
    (REPORTS / "comparison.json").write_text(json.dumps(result, indent=2))

    print(f"applications: {len(scored)}  (subdomains excluded: no progress series yet)")
    print(f"social block share of weight in B: {result['social_block_share_in_B']:.3f}\n")
    print("cross-occupation rank agreement, final year")
    for k, v in result["final_year_rank_agreement"].items():
        print(f"  {k:<24} spearman {v:.4f}")
    print(f"\nA vs B by year: " + ", ".join(f"{y}:{v:.3f}" for y, v in list(result["by_year_rank_agreement"].items())[-6:]))
    print(f"\nwrote {REPORTS}")


if __name__ == "__main__":
    main()
