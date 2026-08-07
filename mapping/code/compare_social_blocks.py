"""
compare_social_blocks.py — which social block should DAIOE carry, and does the discount survive it?

The construction is an ability backbone (52 O*NET abilities) plus one *social block*. Three
candidates occupy that slot, and the discount is on or off, giving six specifications:

    none        no social block                      the published shape
    skills6     the six O*NET social skills          what the appendix matrix added
    acts17      O*NET element 4.A.4 'Interacting With Others', 17 work activities

The six skills and the seventeen activities are alternatives, never both: persuasion and selling or
influencing, negotiation and resolving conflicts, instructing and training and teaching are the same
work counted twice.

Why the activities are the better candidate on paper: they separate leadership, care, negotiation,
service and teaching, which the six skills compress into a single intensity; they are *activities*
rather than worker attributes, so they sit closer to tasks, which is what a task-based measure wants;
and they are O*NET's own published branch rather than anyone's curation of it.

Judged against Eloundou et al.'s human-rated exposure, **on the language-modelling sub-index**. That
restriction is the whole point: DAIOE allapps aggregates vision and games, Eloundou measures LLM
exposure, and comparing them made the discount look decisive when it is not
(`notes/DECISION-discount-external-validation_2026-08-07.md`). Decision rule fixed in advance: a
specification retires the discount only by beating 0.7617 against human_E1 on the sub-index.

Face-validity check, stated before running: representing social work properly should make **clergy
more protected** and **customer service more exposed**.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr

MAP = Path(__file__).resolve().parents[1]
ROOT = MAP.parent
OUT, RAW = ROOT / "data" / "out", MAP / "raw_data"
REPORTS = MAP / "reports" / "variants_2024"
REPORTS.mkdir(parents=True, exist_ok=True)

_spec = importlib.util.spec_from_file_location("bv", MAP / "code" / "build_2024_variants.py")
bv = importlib.util.module_from_spec(_spec)
sys.modules["bv"] = bv
_spec.loader.exec_module(bv)

BEAT = 0.7617      # the pre-stated bar: 52 abilities, no discount, vs human_E1 on the sub-index


def merged_matrix(elements: pd.DataFrame) -> pd.DataFrame:
    """The 13 x 75 matrix, assembled from the three scoring runs and renamed to canonical names."""
    core = pd.read_csv(MAP / "output" / "mapping_matrix_claude_v2026.csv", index_col=0)
    conv = pd.read_csv(MAP / "output" / "mapping_matrix_claude_vconv.csv", index_col=0)
    acts = pd.read_csv(MAP / "output" / "mapping_matrix_claude_vacts.csv", index_col=0)
    for d in (core, conv, acts):
        d.columns = [int(c) for c in d.columns]
    m = pd.concat([core, conv]).sort_index().join(acts, how="left")
    id2canon = dict(zip(elements.ability_id, elements.ability_name.map(bv._canon)))
    return m.rename(columns=id2canon)


def activity_weights(elements: pd.DataFrame) -> pd.DataFrame:
    """4.A.4 occupation weights, renamed from Element ID to the canonical activity name."""
    w = bv.load_activity_weights()
    acts = elements[elements.block == "activity"]
    return w.rename(columns=dict(zip(acts.element_id, acts.ability_name.map(bv._canon))))


def main() -> None:
    elements = pd.read_csv(RAW / "abilities_v2.csv")
    apps = pd.read_csv(RAW / "applications_v2.csv")
    progress = bv.load_progress()
    social_score = bv.load_social_score(2.0)

    M = merged_matrix(elements)
    M.index = apps.set_index("ai_app_id").loc[M.index, "frs_row"].str.strip().str.lower()

    w52, w58 = bv.load_weights(None)
    w69 = bv.combine(w52, activity_weights(elements), None)
    blocks = {"none": w52, "skills6": w58, "acts17": w69}

    el = pd.read_stata(ROOT / "data" / "raw" / "openai_2024_exposure_soc2010.dta").set_index("occ_code_soc2010")
    lm = progress[progress.application == "language modeling"]

    def agree(panel: pd.DataFrame) -> tuple[float, float]:
        p = panel[panel.year == panel.year.max()].copy()
        p["soc"] = p.occ_code_onet.str[:7]
        j = pd.concat([p.groupby("soc").exp_cumul.mean().rename("o"),
                       el[["human_E1", "human_E1_E2"]]], axis=1).dropna()
        return spearmanr(j.o, j.human_E1).statistic, spearmanr(j.o, j.human_E1_E2).statistic

    results, panels = {}, {}
    print("Agreement with Eloundou human ratings, language-modelling sub-index (like-for-like)\n")
    print(f"  {'social block':<12}{'discount':>10}{'vs human_E1':>13}{'vs E1+E2':>11}   {'beats ' + str(BEAT) + '?':>14}")
    for name, W in blocks.items():
        for disc_label, disc in (("on", social_score), ("off", None)):
            panel = bv.build_panel(M, W, lm, disc, 10.0)
            e1, e2 = agree(panel)
            key = f"{name}/{disc_label}"
            panels[key] = bv.build_panel(M, W, progress, disc, 10.0)   # allapps version, for profiles
            results[key] = {"human_E1": round(float(e1), 4), "human_E1_E2": round(float(e2), 4)}
            flag = "YES" if e1 > BEAT else ""
            print(f"  {name:<12}{disc_label:>10}{e1:>13.4f}{e2:>11.4f}   {flag:>14}")

    # ---- the face-validity check, stated before the run ----
    titles = (pd.read_parquet(OUT / "onet_abilities_weighted.parquet")
              .drop_duplicates("occ_code_onet").set_index("occ_code_onet")["Title"])
    watch = {"Clergy": "should become MORE protected",
             "Customer Service Representatives": "should become MORE exposed"}
    print("\n\nFace validity: percentile of cumulative exposure, allapps\n")
    print(f"  {'occupation':<36}" + "".join(f"{k:>16}" for k in panels))
    rows = {}
    for occ, _ in watch.items():
        codes = [c for c in titles.index if str(titles[c]).strip() == occ]
        line = f"  {occ:<36}"
        rows[occ] = {}
        for key, p in panels.items():
            f = p[p.year == p.year.max()].set_index("occ_code_onet").exp_cumul
            pct = f.rank(pct=True)
            v = float(pct.reindex(codes).mean())
            rows[occ][key] = round(v, 3)
            line += f"{v:>16.3f}"
        print(line)
    for occ, note in watch.items():
        print(f"    {occ}: {note}")

    (REPORTS / "social_block_comparison.json").write_text(json.dumps(
        {"bar": BEAT, "agreement": results, "face_validity_percentiles": rows}, indent=2))
    print(f"\nwrote {REPORTS / 'social_block_comparison.json'}")


if __name__ == "__main__":
    main()
