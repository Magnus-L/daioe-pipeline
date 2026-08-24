"""Execute the 24 Aug evening decisions: TheAgentCompany at 95 with the environment
pinned, and GDPval admitted (Tier A, parity-by-construction).

Decisions (Lodefalk & Engberg, 24 Aug 2026): D4(i) TheAgentCompany's ceiling anchor
moves from the degenerate 100.0 to 95.0 (the SWE-bench convention-by-analogy) and the
series is pinned to the Claude-3.5-Sonnet simulation environment, excluding the two
rows measured in other environments (which would book an environment change as a
capability jump: their frontier reads 52.4 against the pinned 43.2). D4(ii) the
instrument-ceiling kind is ratified. GDPval enters as the next Tier-A admission with
the new parity-by-construction anchor kind: its scale is a win rate against human
professionals, so 50 is parity by definition, the cleanest anchor on the slate.

Outputs: extension_agentcompany95_2026-08-24.xlsx and extension_gdpval_2026-08-24.xlsx
with provenance sidecars; the TheAgentCompany anchor row UPDATED in place (100 -> 95,
status convention-by-analogy); a GDPval anchor row appended; freeze-history checks
(must print 0.00e+00).
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
PARENT_AG = "Agentic task execution"

TAC_METRIC = "Agentic work-task resolution on TheAgentCompany"
GDP_METRIC = "Win rate against human professionals on GDPval"


def build_tac95() -> Path:
    src = pd.read_csv(DUMP / "the_agent_company_external.csv")
    pinned = src[src["Environment model"] == "Claude 3.5 Sonnet"].copy()
    dates = pd.to_datetime(pinned["Release date"], errors="coerce")
    keep = dates.notna() & (dates.dt.year >= 2024)
    measures = pd.DataFrame(
        {
            "parent_name": PARENT_AG,
            "metrics_name": TAC_METRIC,
            "papername": "Epoch AI, benchmark data, CC BY 4.0 (externally collected; "
                         "Claude-3.5-Sonnet environment only, decision 24 Aug 2026)",
            "name": pinned.loc[keep, "Model version"],
            "date": dates[keep].dt.strftime("%Y-%m-%d"),
            "value": pinned.loc[keep, "% Score"].astype(float) * 100.0,
        }
    ).dropna(subset=["value"]).sort_values("date").reset_index(drop=True)
    metrics = pd.DataFrame([{
        "metrics_name": TAC_METRIC, "parent_name": PARENT_AG,
        "axis_label": "Percentage correct", "scale": "Percentage correct",
        "target": 95.0,
        "target_label": "Human-resolvable ceiling, convention-by-analogy (SWE-bench rule)",
        "target_source": "Decision 24 Aug 2026; upgrade when the maintainers supply a task-error estimate",
        "protocol": "system_level", "chain_year": 2024,
        "source": "Epoch AI (CC BY 4.0), external; environment pinned", "retrieved": RETRIEVED,
    }])
    out = ROOT / "data" / "updates" / "extension_agentcompany95_2026-08-24.xlsx"
    with pd.ExcelWriter(out) as xw:
        measures.to_excel(xw, sheet_name="measures", index=False)
        metrics.to_excel(xw, sheet_name="metrics", index=False)
    dropped = int(len(src) - len(measures))
    print(f"wrote {out.relative_to(ROOT)}: {len(measures)} observations "
          f"({dropped} foreign-environment/undated rows excluded), anchor 95.0")
    prov = {
        "source": "Epoch AI", "url": "https://epoch.ai/data/benchmark_data.zip",
        "licence": "CC BY 4.0", "retrieved": RETRIEVED, "evaluation": "external",
        "files": {"the_agent_company_external.csv": {
            "sha256": hashlib.sha256((DUMP / "the_agent_company_external.csv").read_bytes()).hexdigest(),
            "rows": int(len(src))}},
        "protocol_note": ("Environment pinned to Claude 3.5 Sonnet (14 of 16 rows); the two "
                          "rows in other environments (best 52.4 vs 43.2) excluded so an "
                          "environment change is never booked as capability. Anchor 95.0 by "
                          "the SWE-bench convention-by-analogy, decision 24 Aug 2026."),
    }
    (ROOT / "data" / "updates" / "provenance_agentcompany95_2026-08-24.json").write_text(
        json.dumps(prov, indent=2))
    return out


def build_gdpval() -> Path:
    src = pd.read_csv(DUMP / "gdpval_external.csv") if (DUMP / "gdpval_external.csv").exists() \
        else pd.read_csv(DUMP / "gdpval.csv")
    score_col = [c for c in src.columns if "win" in c.lower()][0]
    dates = pd.to_datetime(src["Release date"], errors="coerce")
    keep = dates.notna() & (dates.dt.year >= 2024)
    vals = src.loc[keep, score_col].astype(float)
    mult = 100.0 if vals.max() <= 1.5 else 1.0
    measures = pd.DataFrame(
        {
            "parent_name": PARENT_AG,
            "metrics_name": GDP_METRIC,
            "papername": "Epoch AI, benchmark data, CC BY 4.0 (externally collected)",
            "name": src.loc[keep, "Model version"],
            "date": dates[keep].dt.strftime("%Y-%m-%d"),
            "value": vals * mult,
        }
    ).dropna(subset=["value"]).sort_values("date").reset_index(drop=True)
    metrics = pd.DataFrame([{
        "metrics_name": GDP_METRIC, "parent_name": PARENT_AG,
        "axis_label": "Percentage correct", "scale": "Percentage correct",
        "target": 50.0,
        "target_label": "Parity by construction: 50% win rate against human professionals",
        "target_source": "the benchmark's own scoring definition (win rate vs human experts)",
        "protocol": "system_level", "chain_year": 2024,
        "source": "Epoch AI (CC BY 4.0), external", "retrieved": RETRIEVED,
    }])
    out = ROOT / "data" / "updates" / "extension_gdpval_2026-08-24.xlsx"
    with pd.ExcelWriter(out) as xw:
        measures.to_excel(xw, sheet_name="measures", index=False)
        metrics.to_excel(xw, sheet_name="metrics", index=False)
    print(f"wrote {out.relative_to(ROOT)}: {len(measures)} observations "
          f"(multiplier {mult}), anchor 50.0 parity-by-construction")
    prov = {
        "source": "Epoch AI", "url": "https://epoch.ai/data/benchmark_data.zip",
        "licence": "CC BY 4.0", "retrieved": RETRIEVED, "evaluation": "external",
        "files": {Path(src.attrs.get('path', 'gdpval')).name if hasattr(src, 'attrs') else "gdpval": {
            "rows": int(len(src))}},
        "protocol_note": ("Win rate against human professionals on real economically valuable "
                          "tasks; 50 is parity by definition, hence the parity-by-construction "
                          "anchor kind (ratified 24 Aug 2026)."),
    }
    (ROOT / "data" / "updates" / "provenance_gdpval_2026-08-24.json").write_text(
        json.dumps(prov, indent=2))
    return out


def update_anchors() -> None:
    a = pd.read_csv(ANCHORS)
    m = a["metrics_name"] == TAC_METRIC
    assert m.any(), "TheAgentCompany anchor row not found"
    a.loc[m, "anchor"] = 95.0
    a.loc[m, "status"] = "convention-by-analogy"
    a.loc[m, "evidence"] = (
        "Decision 24 Aug 2026 (Lodefalk & Engberg): 95.0 by the SWE-bench convention "
        "(100 minus a residual task-defect allowance), replacing the degenerate 100.0 "
        "whose information weight was 2.5e-06. The anchor choice cannot alter the "
        "series' measured progress (the anchor cancels out of within-series changes); "
        "it only restores the instrument's weight. Environment pinned to Claude 3.5 "
        "Sonnet in the same decision. Upgrade when the maintainers supply an actual "
        "task-error estimate.")
    if not (a["metrics_name"] == GDP_METRIC).any():
        a = pd.concat([a, pd.DataFrame([{
            "metrics_name": GDP_METRIC, "parent_name": PARENT_AG,
            "scale": "Percentage correct", "anchor": 50.0,
            "anchor_kind": "parity-by-construction", "category": "B",
            "source": "the benchmark's own scoring definition (win rate vs human professionals)",
            "evidence": ("The scale is a win rate against human professionals, so 50 IS "
                         "parity by definition; no external baseline needs verifying. "
                         "Kind ratified 24 Aug 2026."),
            "status": "verified",
        }])], ignore_index=True)
    a.to_csv(ANCHORS, index=False)
    print(f"anchors updated: TheAgentCompany -> 95.0; GDPval appended ({len(a)} anchors)")


def _slopes(raw: dict) -> pd.DataFrame:
    cfg = cfgmod.Config(raw=raw, root=ROOT)
    measures = s2._build_measures(cfg)
    formated = s2.build_formated_data(cfg)
    frontiers = s2.build_metrics_frontiers(cfg, formated, measures)
    return s2.build_slopes(cfg, frontiers)


def freeze_history_check(workbooks: list[Path]) -> None:
    raw = yaml.safe_load((ROOT / "config-refresh2024.yaml").read_text())
    raw["year_final"] = 2025
    a = _slopes({**raw})
    b = _slopes({**raw, "benchmark_extensions": [str(p.relative_to(ROOT)) for p in workbooks]})
    win = lambda df: (
        df[(df["year"] >= 2010) & (df["year"] <= 2023) & (df["parent_name"] != "robotics")]
        .set_index(["parent_name", "year"])[["mean", "count"]].sort_index())
    wa, wb = win(a), win(b)
    assert wa.index.equals(wb.index)
    dmean = (wa["mean"] - wb["mean"]).abs().max()
    dcount = (wa["count"] - wb["count"]).abs().max()
    print(f"freeze-history [tac95+gdpval jointly]: {len(wa)} application-years, "
          f"max |d progress| = {dmean:.2e}, max |d basket count| = {dcount:.0f}")
    if dmean != 0.0 or dcount != 0.0:
        raise SystemExit("FREEZE-HISTORY VIOLATION")


if __name__ == "__main__":
    wbs = [build_tac95(), build_gdpval()]
    update_anchors()
    freeze_history_check(wbs)
