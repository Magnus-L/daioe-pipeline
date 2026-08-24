"""Epoch admission round, 24 Aug 2026: two staged extensions + one anchor repair.

Magnus asked (24 Aug) for an Epoch admission round per surviving application and a
thickening of the four one-benchmark applications. This script builds the two series
that are admissible TODAY, i.e. whose human anchors are documented in the literature
and were verified with quoted evidence this morning. Everything else on the candidate
slate needs anchor research first (see the meeting hand-out). The workbooks are
STAGED: built, gate-checked, and left in data/updates/ for the meeting to decide
whether they enter the v1.1.0 assembly (decisions D5c and D8). Nothing here touches
any vintage.

Series 1 -- OSWorld (thickens Agentic task execution to two instruments):
  * SOURCE: os_world_external.csv from Epoch's benchmark_data.zip, retrieved
    2026-08-24. EXTERNAL collection: scores as reported on the benchmark's own
    leaderboard, mixed agent scaffolds and step budgets (the `Agent` column carries
    e.g. "claude-sonnet-4-6 (100 steps)"). Declared system_level with a protocol
    note, the TheAgentCompany precedent. Undated leaderboard rows are dropped.
  * ANCHOR: 72.36, kind human, VERIFIED 2026-08-24 against arXiv:2404.07972
    (abstract): "While humans can accomplish over 72.36% of the tasks, the best
    model achieves only 12.24% success". "over" makes 72.36 a lower bound on human
    performance, hence status verified-conservative.
  * Unlike METR this anchors agentic in success-rate space, so it is the second,
    methodologically independent instrument the corroboration check wants.

Series 2 -- MATH Level 5 (thickens Mathematical and scientific reasoning to two):
  * SOURCE: math_level_5.csv, Epoch-RUN harness (mean_score, stderr, Inspect logs),
    so pure_model, one protocol. Observations before the 2024 chain year (11 rows
    from 2023) are dropped per the chain discipline; they are never written
    backwards.
  * ANCHOR: 90.0, kind human-expert, VERIFIED 2026-08-24 against arXiv:2103.03874
    (Hendrycks et al., Introduction): "We also evaluated humans on MATH, and found
    that a computer science PhD student who does not especially like mathematics
    attained approximately 40% on MATH, while a three-time IMO gold medalist
    attained 90%". CAVEAT: measured on the full MATH test set; this series covers
    Level 5 (the hardest band) only -- status verified-metric-ambiguous.
  * KNOWN LIMIT: the frontier is near-saturated (96->98 per cent within 2025), so
    this series adds precision and corroboration to the GPQA basket, not increment.

Repair -- GPQA Diamond anchor row: the two GPQA builders never ran append_anchor(),
so the 81.3 anchor lives only in the workbook metrics sheets and the anchors file
drifted. The row is appended here from the workbook's own declared fields, with the
selection caveat from the door note (diamond-set 81.3 is selection-skewed; the
unbiased extended-set figure is 64.8).

Outputs:
  data/updates/extension_osworld_2026-08-24.xlsx      + provenance json
  data/updates/extension_mathlevel5_2026-08-24.xlsx   + provenance json
  three rows appended to data/derived/human_anchors_v1.csv (idempotent)
  freeze-history checks printed per workbook and jointly (must be 0.00e+00)
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daioe import config as cfgmod  # noqa: E402
from daioe import stage2_ai_progress as s2  # noqa: E402

DUMP = ROOT / "data" / "updates" / "epoch_dump_20260824"
ANCHORS = ROOT / "data" / "derived" / "human_anchors_v1.csv"
RETRIEVED = "2026-08-24"

SERIES = [
    {
        "tag": "osworld",
        "csv": "os_world_external.csv",
        "parent": "Agentic task execution",
        "metric": "Desktop computer-use task completion on OSWorld",
        "papername": "Epoch AI, benchmark data, CC BY 4.0 (externally collected leaderboard scores)",
        "score_col": "Score",
        "multiplier": 1.0,          # already in per cent
        "protocol": "system_level",
        "target": 72.36,
        "target_label": "Human success rate (lower bound), OSWorld paper abstract",
        "target_source": "arXiv:2404.07972 abstract",
        "protocol_note": (
            "External collection: scores as reported on os-world.github.io, gathered by "
            "Epoch; mixed agent scaffolds and step budgets (Agent column, e.g. "
            "'claude-sonnet-4-6 (100 steps)'). Declared system_level per the "
            "TheAgentCompany precedent; undated leaderboard rows dropped."
        ),
        "evaluation": "external",
        "anchor_row": {
            "scale": "Percentage correct",
            "anchor": 72.36,
            "anchor_kind": "human",
            "category": "B",
            "source": "Xie et al., OSWorld, arXiv:2404.07972 (abstract; verified 2026-08-24)",
            "evidence": (
                '"While humans can accomplish over 72.36% of the tasks, the best model '
                'achieves only 12.24% success". The "over" makes 72.36 a lower bound on '
                "human performance; conservative reading."
            ),
            "status": "verified-conservative",
        },
    },
    {
        "tag": "mathlevel5",
        "csv": "math_level_5.csv",
        "parent": "Mathematical and scientific reasoning",
        "metric": "Competition mathematics on MATH Level 5",
        "papername": "Epoch AI, benchmark data, CC BY 4.0 (Epoch-run harness, Inspect logs)",
        "score_col": "mean_score",
        "multiplier": 100.0,        # stored as 0-1 proportion
        "protocol": "pure_model",
        "target": 90.0,
        "target_label": "Three-time IMO gold medalist on the full MATH test set",
        "target_source": "arXiv:2103.03874 Introduction",
        "protocol_note": (
            "Epoch-run harness (mean_score with stderr and Inspect logs), one protocol. "
            "Observations predating the 2024 chain year are excluded per the chain "
            "discipline. Frontier near-saturated within 2025 (96->98 per cent): the "
            "series' role in the basket is precision and corroboration, not increment."
        ),
        "evaluation": "epoch-run",
        "anchor_row": {
            "scale": "Percentage correct",
            "anchor": 90.0,
            "anchor_kind": "human-expert",
            "category": "B",
            "source": "Hendrycks et al., MATH, arXiv:2103.03874 (Introduction; verified 2026-08-24)",
            "evidence": (
                '"We also evaluated humans on MATH, and found that a computer science PhD '
                "student who does not especially like mathematics attained approximately 40% "
                "on MATH, while a three-time IMO gold medalist attained 90%, indicating that "
                'MATH can be challenging for humans as well." CAVEAT: measured on the full '
                "MATH test set; this series covers Level 5, the hardest band, only."
            ),
            "status": "verified-metric-ambiguous",
        },
    },
]

GPQA_ANCHOR_ROW = {
    "metrics_name": "Graduate-level QA on GPQA Diamond",
    "parent_name": "Mathematical and scientific reasoning",
    "scale": "Percentage correct",
    "anchor": 81.3,
    "anchor_kind": "human-expert",
    "category": "B",
    "source": "arXiv:2311.12022 Table 2 (copied from the workbook's declared fields, 2026-08-24)",
    "evidence": (
        "Expert human accuracy 81.3 on the Diamond subset, per the workbook declaration "
        "(extension_gpqa_maths_2026-08-08.xlsx) whose builders never ran append_anchor(). "
        "CAVEAT from the door note: the diamond-set 81.3 is selection-skewed (questions "
        "kept partly because validators solved them); the unbiased extended-set figure "
        "is 64.8."
    ),
    "status": "verified-metric-ambiguous",
}


def build_workbook(spec: dict) -> Path:
    src = pd.read_csv(DUMP / spec["csv"])
    dates = pd.to_datetime(src["Release date"], errors="coerce")
    keep = dates.notna() & (dates.dt.year >= 2024)
    dropped = int((~keep).sum())
    measures = pd.DataFrame(
        {
            "parent_name": spec["parent"],
            "metrics_name": spec["metric"],
            "papername": spec["papername"],
            "name": src.loc[keep, "Model version"],
            "date": dates[keep].dt.strftime("%Y-%m-%d"),
            "value": src.loc[keep, spec["score_col"]].astype(float) * spec["multiplier"],
        }
    ).dropna(subset=["value"]).sort_values("date").reset_index(drop=True)
    metrics = pd.DataFrame(
        [
            {
                "metrics_name": spec["metric"],
                "parent_name": spec["parent"],
                "axis_label": "Percentage correct",
                "scale": "Percentage correct",
                "target": spec["target"],
                "target_label": spec["target_label"],
                "target_source": spec["target_source"],
                "protocol": spec["protocol"],
                "chain_year": 2024,
                "source": f"Epoch AI (CC BY 4.0), {spec['evaluation']}",
                "retrieved": RETRIEVED,
            }
        ]
    )
    out_xlsx = ROOT / "data" / "updates" / f"extension_{spec['tag']}_{RETRIEVED}.xlsx"
    with pd.ExcelWriter(out_xlsx) as xw:
        measures.to_excel(xw, sheet_name="measures", index=False)
        metrics.to_excel(xw, sheet_name="metrics", index=False)
    print(f"wrote {out_xlsx.relative_to(ROOT)}: {len(measures)} observations "
          f"({dropped} pre-chain or undated rows dropped), 1 declaration")

    prov = {
        "source": "Epoch AI",
        "url": "https://epoch.ai/data/benchmark_data.zip",
        "licence": "CC BY 4.0",
        "retrieved": RETRIEVED,
        "evaluation": spec["evaluation"],
        "files": {
            spec["csv"]: {
                "sha256": hashlib.sha256((DUMP / spec["csv"]).read_bytes()).hexdigest(),
                "rows": int(len(src)),
            }
        },
        "protocol_note": spec["protocol_note"],
    }
    out_prov = ROOT / "data" / "updates" / f"provenance_{spec['tag']}_{RETRIEVED}.json"
    out_prov.write_text(json.dumps(prov, indent=2))
    print(f"wrote {out_prov.relative_to(ROOT)}")
    return out_xlsx


def append_anchor(metric: str, parent: str, row: dict) -> None:
    anchors = pd.read_csv(ANCHORS)
    if (anchors["metrics_name"] == metric).any():
        print(f"anchor row already present for {metric}; not duplicated")
        return
    full = {"metrics_name": metric, "parent_name": parent, **row}
    anchors = pd.concat([anchors, pd.DataFrame([full])], ignore_index=True)
    anchors.to_csv(ANCHORS, index=False)
    print(f"anchor row appended for {metric} ({len(anchors)} anchors)")


def _slopes(raw: dict) -> pd.DataFrame:
    cfg = cfgmod.Config(raw=raw, root=ROOT)
    measures = s2._build_measures(cfg)
    formated = s2.build_formated_data(cfg)
    frontiers = s2.build_metrics_frontiers(cfg, formated, measures)
    return s2.build_slopes(cfg, frontiers)


def freeze_history_check(workbooks: list[Path], label: str) -> None:
    raw = yaml.safe_load((ROOT / "config-refresh2024.yaml").read_text())
    raw["year_final"] = 2025

    a = _slopes({**raw})
    b = _slopes({**raw, "benchmark_extensions": [str(p.relative_to(ROOT)) for p in workbooks]})

    win = lambda df: (
        df[(df["year"] >= 2010) & (df["year"] <= 2023) & (df["parent_name"] != "robotics")]
        .set_index(["parent_name", "year"])[["mean", "count"]]
        .sort_index()
    )
    wa, wb = win(a), win(b)
    assert wa.index.equals(wb.index), "published application-years differ in membership"
    dmean = (wa["mean"] - wb["mean"]).abs().max()
    dcount = (wa["count"] - wb["count"]).abs().max()
    print(f"freeze-history [{label}]: {len(wa)} application-years, "
          f"max |d progress| = {dmean:.2e}, max |d basket count| = {dcount:.0f}")
    if dmean != 0.0 or dcount != 0.0:
        raise SystemExit("FREEZE-HISTORY VIOLATION: the extension changed published values")

    for spec in SERIES:
        panel = b[b["parent_name"] == spec["parent"]]
        if len(panel):
            print(f"\n{spec['parent']} panel (with the staged series):")
            print(panel[["year", "parent_name", "count", "mean"]].to_string(index=False))


if __name__ == "__main__":
    built = [build_workbook(s) for s in SERIES]
    for s in SERIES:
        append_anchor(s["metric"], s["parent"], s["anchor_row"])
    append_anchor(GPQA_ANCHOR_ROW["metrics_name"], GPQA_ANCHOR_ROW["parent_name"],
                  {k: v for k, v in GPQA_ANCHOR_ROW.items()
                   if k not in ("metrics_name", "parent_name")})
    for wb, s in zip(built, SERIES):
        freeze_history_check([wb], s["tag"])
    freeze_history_check(built, "both jointly")
