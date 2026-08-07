"""
threshold_validate.py — does the level-threshold construction earn adoption?

Parallel track; reads only, writes only to `mapping/reports/threshold_track/`.

Decision rule, fixed before the run (`notes/EXPLORATION-level-thresholds-and-criticality`):
adopt only if the integrated measure BOTH

  1. beats **0.7617** against `human_E1` on the like-for-like language-modelling sub-index, which is
     the current best (52 abilities, relatedness, no discount), and
  2. preserves the face-validity ordering
     telemarketers > customer service > clergy > mental health counsellors > clinical psychologists.

Beating one but not the other adopts nothing.

Why the sub-index and not allapps: DAIOE allapps aggregates vision and games while Eloundou measures
LLM exposure, and comparing them made the discount look decisive when a like-for-like comparison
showed it was not (`notes/DECISION-discount-external-validation_2026-08-07.md`). Repeating that
mistake here would be worse, because the threshold changes the relatedness term itself.

The ablation reports abilities-only, activities-only and both, so if the result moves we know which
block moved it.
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
REPORTS = MAP / "reports" / "threshold_track"

BAR = 0.7617
FACE = ["Telemarketers", "Customer Service Representatives", "Clergy",
        "Mental Health Counselors", "Clinical Psychologists"]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, MAP / "code" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


bv, tw, tp = _load("build_2024_variants"), _load("threshold_weights"), _load("threshold_panel")


def agreement(panel: pd.DataFrame, el: pd.DataFrame) -> tuple[float, float, int]:
    p = panel[panel.year == panel.year.max()].copy()
    p["soc"] = p.occ_code_onet.str[:7]
    j = pd.concat([p.groupby("soc").exp_cumul.mean().rename("o"),
                   el[["human_E1", "human_E1_E2"]]], axis=1).dropna()
    return spearmanr(j.o, j.human_E1).statistic, spearmanr(j.o, j.human_E1_E2).statistic, len(j)


def main() -> None:
    elements = pd.read_csv(MAP / "raw_data" / "abilities_v2.csv")
    apps = pd.read_csv(MAP / "raw_data" / "applications_v2.csv")
    app_names = dict(zip(apps.ai_app_id, apps.frs_row.str.strip().str.lower()))
    el = pd.read_stata(ROOT / "data" / "raw" / "openai_2024_exposure_soc2010.dta").set_index("occ_code_soc2010")
    progress = bv.load_progress()
    lm = progress[progress.application == "language modeling"]
    titles = (pd.read_parquet(ROOT / "data" / "out" / "onet_abilities_weighted.parquet")
              .drop_duplicates("occ_code_onet").set_index("occ_code_onet")["Title"])

    combos = [["ability"], ["activity"], ["ability", "activity"],
              ["ability", "social_skill"], ["ability", "social_skill", "activity"]]
    steeps = [0.5, 1.0, 2.0]

    results, panels = [], {}
    for blocks in combos:
        try:
            required, weight = tw.load(blocks, elements)
            attained = tp.load_attained(blocks, elements)
        except SystemExit:
            continue
        if not set(attained.columns) & set(required.columns):
            continue
        for k in steeps:
            A = tp.reach(attained, required, weight, k)
            panel = tp.build(A, lm, app_names)
            e1, e2, n = agreement(panel, el)
            key = f"{'+'.join(blocks)} k={k}"
            panels[key] = tp.build(A, progress, app_names)      # allapps version, for face validity
            results.append({"blocks": "+".join(blocks), "steepness": k,
                            "human_E1": round(float(e1), 4), "human_E1_E2": round(float(e2), 4),
                            "n": n, "beats_bar": bool(e1 > BAR)})

    tab = pd.DataFrame(results).sort_values("human_E1", ascending=False)
    print(f"Like-for-like agreement with Eloundou, language-modelling sub-index. Bar to beat: {BAR}\n")
    print(tab.to_string(index=False))

    best = tab.iloc[0]
    key = f"{best.blocks} k={best.steepness}"
    print(f"\n\nFace validity for the best specification ({key})\n")
    f = panels[key]
    f = f[f.year == f.year.max()].set_index("occ_code_onet").exp_cumul
    pct = f.rank(pct=True)
    order, seen = [], []
    for nm in FACE:
        codes = [c for c in titles.index if str(titles[c]).strip() == nm]
        v = float(pct.reindex(codes).mean()) if codes else float("nan")
        seen.append(v)
        order.append({"occupation": nm, "percentile": round(v, 3)})
        print(f"  {nm:<36} {v:.3f}")
    monotone = all(a >= b for a, b in zip(seen, seen[1:]))
    print(f"\n  ordering preserved: {'YES' if monotone else 'NO'}")

    verdict = ("ADOPT" if bool(best.beats_bar) and monotone else
               "DO NOT ADOPT — " + ("fails the ordering" if best.beats_bar else
                                    f"fails the bar ({best.human_E1:.4f} vs {BAR})"))
    print(f"\n  DECISION: {verdict}")

    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "validation.json").write_text(json.dumps(
        {"bar": BAR, "results": results, "best": key,
         "face_validity": order, "ordering_preserved": monotone, "verdict": verdict}, indent=2))
    print(f"\nwrote {REPORTS / 'validation.json'}")


if __name__ == "__main__":
    main()
