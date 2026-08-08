"""Build the conversation extension workbook: Theory of Mind on ToMBench, chained 2024.

The conversation application (EFF parent "Turing test for casual conversation", id 3)
has sat in the DAIOE id maps since the original build but never carried a usable
progress series; it is one of the never-used applications whose mapping-matrix row
now exists (mapping_matrix_claude_v2026.csv). This script gives it its first series,
which the charter (notes/CHARTER-daioe-2025_2026-08-07.md §3) names as the one
missing input for the social block's time dimension.

Series design, from the two Category A reads of 8 Aug 2026:

* The BENCHMARK is ToMBench (Chen et al., ACL 2024, 2024.acl-long.847): 2,860
  multiple-choice questions over 8 theory-of-mind tasks and 31 ATOMS abilities,
  built from scratch to avoid training-data contamination, data under MIT. Its
  human baseline is organiser-produced: 20 native graduate students completed the
  full Chinese inventory; ability view 86.1, task view 85.4 (Tables 2-3).

* The OBSERVATIONS all come from ONE follow-up evaluation under ONE protocol:
  arXiv:2602.10625 ("To Think or Not To Think", v3 Mar 2026), Table 1 -- nine
  models, temperature 0, top-p 1, max 2048 tokens. Single-source discipline is
  deliberate: it is what makes the series protocol-pure, exactly as the GPQA
  demonstration series is pure by coming only from Epoch's harness.

* COVERAGE VERIFICATION: reconstructing each model's Table 1 overall score as the
  question-count-weighted mean of its six ability-dimension scores (Table 3 of the
  same paper; weights 882/180/420/340/290/748 from ToMBench's Table 18) reproduces
  Table 1 within rounding for every model (e.g. GPT-o3: 0.8177 vs published 0.818).
  So the paper evaluated the FULL 2,860-question benchmark in the ability view,
  and the matching anchor is the ability-view human baseline 86.1.

* DATING follows the pipeline convention (extension_gpqa_2026-08-07.xlsx): an
  observation is dated by its model's public release, because the index measures
  when a capability became available, not when someone measured it. The paper does
  not name the GPT-4o snapshot; every 2024 snapshot gives the same annual
  observation, so the ambiguity cannot reach the index.

* PRE-CHAIN CONTEXT, excluded by guard 6 (no observation before chain year 2024):
  the original paper's own frontier, GPT-4-1106 at 74.0 (En) / 75.3 (Zh) task view,
  models tested 2023. Recorded here so the exclusion is a visible decision.

* ANCHOR CAVEATS, in the GPQA-caveat spirit (a wrong anchor costs information
  weighting, not measurement accuracy): (1) the human baseline was measured on the
  Chinese inventory while the observations are (inferred) English-protocol runs;
  the benchmark authors justify cross-language use citing Bradford et al. (2018)
  that ToM task performance does not differ significantly between native English
  and Chinese speakers. (2) arXiv:2602.10625 does not state the evaluation
  language explicitly; English is inferred from its worked examples.

Outputs:
  data/updates/extension_tombench_2026-08-08.xlsx  (measures + metrics sheets)
  a new row appended to data/derived/human_anchors_v1.csv (idempotent)
  freeze-history check printed: published-window slopes must be IDENTICAL
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daioe import config as cfgmod  # noqa: E402
from daioe import stage2_ai_progress as s2  # noqa: E402

OUT_XLSX = ROOT / "data" / "updates" / "extension_tombench_2026-08-08.xlsx"
ANCHORS = ROOT / "data" / "derived" / "human_anchors_v1.csv"

PARENT = "Turing test for casual conversation"
METRIC = "Theory of Mind on ToMBench"
PAPERNAME = "arXiv:2602.10625 Table 1, full ToMBench (2,860 Q), temp 0"

# (model name as printed in the source table, public release date, accuracy in %)
# Values verified directly against the PDF's Table 1 row "ToMBench" on 8 Aug 2026;
# a first-pass automated extraction had misaligned the columns, so each value below
# was re-read by eye against the model-column header order.
OBSERVATIONS = [
    ("GPT-4o",               "2024-05-13", 79.7),
    ("DeepSeek-V3",          "2024-12-26", 76.3),
    ("DeepSeek-R1",          "2025-01-20", 80.1),
    ("GPT-o4-mini",          "2025-04-16", 80.3),
    ("GPT-o3",               "2025-04-16", 81.8),
    ("Qwen3-8B",             "2025-04-29", 67.4),
    ("Qwen3-8B-Reasoning",   "2025-04-29", 72.9),
    ("Qwen3-32B",            "2025-04-29", 75.4),
    ("Qwen3-32B-Reasoning",  "2025-04-29", 77.5),
]

ANCHOR_ROW = {
    "metrics_name": METRIC,
    "parent_name": PARENT,
    "scale": "Percentage correct",
    "anchor": 86.1,
    "anchor_kind": "human",
    "category": "A",
    "source": "Chen et al., ToMBench, ACL 2024.acl-long.847, Table 3",
    "evidence": (
        '"we recruit 20 native graduate students (each paid with $15) to complete '
        'the Chinese ToMBench together ... We directly use this result as human '
        'performance"; Table 3 Human row: 86.1 (ability view). '
        "Ability view chosen because the observation source (arXiv:2602.10625) is "
        "verified full-benchmark by weighted reconstruction of its Table 1 from its "
        "Table 3 dimensions."
    ),
    "status": "verified",
}


def build_workbook() -> None:
    measures = pd.DataFrame(
        [
            {
                "parent_name": PARENT,
                "metrics_name": METRIC,
                "papername": PAPERNAME,
                "name": name,
                "date": date,
                "value": value,
            }
            for name, date, value in OBSERVATIONS
        ]
    )
    metrics = pd.DataFrame(
        [
            {
                "metrics_name": METRIC,
                "parent_name": PARENT,
                "axis_label": "Percentage correct",
                "scale": "Percentage correct",
                "target": 86.1,
                "target_label": "Human baseline, ability view (20 graduate students, full inventory)",
                "target_source": "ACL 2024.acl-long.847 Table 3",
                "protocol": "pure_model",
                "chain_year": 2024,
                "source": "ToMBench (MIT); model scores arXiv:2602.10625 Table 1",
                "retrieved": "2026-08-08",
            }
        ]
    )
    with pd.ExcelWriter(OUT_XLSX) as xw:
        measures.to_excel(xw, sheet_name="measures", index=False)
        metrics.to_excel(xw, sheet_name="metrics", index=False)
    print(f"wrote {OUT_XLSX.relative_to(ROOT)}: {len(measures)} observations, 1 declaration")


def append_anchor() -> None:
    anchors = pd.read_csv(ANCHORS)
    if (anchors["metrics_name"] == METRIC).any():
        print("anchor row already present; not duplicated")
        return
    anchors = pd.concat([anchors, pd.DataFrame([ANCHOR_ROW])], ignore_index=True)
    anchors.to_csv(ANCHORS, index=False)
    print(f"anchor row appended to {ANCHORS.relative_to(ROOT)} ({len(anchors)} anchors)")


def _slopes(raw: dict) -> pd.DataFrame:
    cfg = cfgmod.Config(raw=raw, root=ROOT)
    measures = s2._build_measures(cfg)
    formated = s2.build_formated_data(cfg)
    frontiers = s2.build_metrics_frontiers(cfg, formated, measures)
    return s2.build_slopes(cfg, frontiers)


def freeze_history_check() -> None:
    """Admitting the series must change NOTHING in the published window.

    Both runs use year_final 2025 (so the 2025 observations are inside the yearly
    skeleton) and differ only in benchmark_extensions. The published 2010-2023
    application-year slopes (progress 'mean' and basket 'count') must be identical
    to the last bit; the robotics dummy is pinned to year_final by construction and
    is excluded, exactly as in the GPQA demonstration.
    """
    raw = yaml.safe_load((ROOT / "config-refresh2024.yaml").read_text())
    raw["year_final"] = 2025

    a = _slopes({**raw})  # no extension
    raw_ext = {**raw, "benchmark_extensions": [str(OUT_XLSX.relative_to(ROOT))]}
    b = _slopes(raw_ext)

    win = lambda df: (
        df[(df["year"] >= 2010) & (df["year"] <= 2023) & (df["parent_name"] != "robotics")]
        .set_index(["parent_name", "year"])[["mean", "count"]]
        .sort_index()
    )
    wa, wb = win(a), win(b)
    assert wa.index.equals(wb.index), "published application-years differ in membership"
    dmean = (wa["mean"] - wb["mean"]).abs().max()
    dcount = (wa["count"] - wb["count"]).abs().max()
    print(f"freeze-history: {len(wa)} application-years compared, "
          f"max |d progress| = {dmean:.2e}, max |d basket count| = {dcount:.0f}")
    if dmean != 0.0 or dcount != 0.0:
        raise SystemExit("FREEZE-HISTORY VIOLATION: the extension changed published values")

    conv = b[b["parent_name"] == PARENT]
    print("\nconversation application panel (new):")
    print(conv[["year", "parent_name", "count", "mean"]].to_string(index=False))


if __name__ == "__main__":
    build_workbook()
    append_anchor()
    freeze_history_check()
