"""Build the INTERIM agentic extension workbook: TheAgentCompany, chained 2024.

Magnus, 8 Aug 2026: unhappy to wait on METR's licence decision -- substitute until
they respond. This script admits TheAgentCompany (Xu et al., CMU, arXiv:2412.14161:
"Benchmarking LLM Agents on Consequential Real World Tasks") as the agentic
application's interim series. When METR's licence clears, METR becomes the primary
anchor exactly as the b3 subdomain-evidence note designed, with SWE-bench Verified
secondary; this series then remains as corroboration or is retired at the next
chain point, a declared decision either way.

Why TheAgentCompany, of the agentic candidates in Epoch's collection:

* THEMATIC FIT is exact for a labour-economics measure: 175 "diverse, realistic and
  professional tasks in a software [company]", motivated in the paper's own abstract
  by "important implications both for industry looking to adopt AI into their
  workflows and for economic policy to understand the effects that adoption of AI
  may have on the labor market".
* ONE SCAFFOLD: "All models are run with OpenHands agent framework" -- the scores
  are maintainer-produced (the paper's own experiment results, then the benchmark's
  leaderboard), not vendor-self-reported.
* LICENCE: ingested from Epoch's benchmark data collection (CC BY 4.0). The file is
  an Epoch EXTERNAL collection, not an Epoch-run harness; provenance records this,
  per the door's evaluation-kind doctrine.

PROTOCOL PURITY: the simulated company's NPC colleagues are themselves an LLM, and
the environment model changed from Claude 3.5 Sonnet to GPT-4o / Qwen-Plus for the
two most recent leaderboard rows. A changed environment is a changed protocol, so
this series is DECLARED as the Claude-3.5-Sonnet-environment protocol and the two
other-environment rows are excluded (recorded in provenance). They can enter at a
later chain point if the maintainers standardise, or the next vintage re-declares.

METRIC: '% Resolved' (full task completion) x 100, mirroring SWE-bench's resolution
semantics; the partial-credit '% Score' is more scaffold-sensitive and is not used.

ANCHOR: 100.0, human-ceiling, PROVISIONAL (Erik decision 4, ceiling-anchor
convention). Tasks are performable by a human worker by construction: checkpoints
are designed "so that a human worker would be able to complete the task without
asking for further instructions" (paper, section 2). No residual-error estimate
exists (unlike SWE-bench's 5-10%), so the undiscounted ceiling stands with the
degeneracy-under-transform caveat recorded; values (max 33.1 in-protocol) sit far
from the boundary, so the frozen-style construction is unaffected.

Outputs mirror the SWE-bench admission: workbook + provenance sidecar + anchor row
+ freeze-history check (must print 0.00e+00).
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

DUMP_CSV = ROOT / "data" / "updates" / "epoch_dump_20260808" / "the_agent_company_external.csv"
OUT_XLSX = ROOT / "data" / "updates" / "extension_agentcompany_2026-08-08.xlsx"
OUT_PROV = ROOT / "data" / "updates" / "provenance_agentcompany_2026-08-08.json"
ANCHORS = ROOT / "data" / "derived" / "human_anchors_v1.csv"

PARENT = "Agentic task execution"
METRIC = "Agentic work-task resolution on TheAgentCompany"
ENVIRONMENT = "Claude 3.5 Sonnet"
PAPERNAME = ("Epoch AI collection (CC BY 4.0) of TheAgentCompany maintainer results; "
             "OpenHands scaffold, Claude-3.5-Sonnet environment")

ANCHOR_ROW = {
    "metrics_name": METRIC,
    "parent_name": PARENT,
    "scale": "Percentage correct",
    "anchor": 100.0,
    "anchor_kind": "human-ceiling",
    "category": "B",
    "source": "Xu et al., TheAgentCompany, arXiv:2412.14161 (read 2026-08-08)",
    "evidence": (
        'Tasks are human-performable by construction: checkpoints designed "so that a '
        'human worker would be able to complete the task without asking for further '
        'instructions"; "175 diverse, realistic and professional tasks in a software '
        'company". No residual-error estimate published (unlike SWE-bench), so the '
        "undiscounted ceiling stands. PROVISIONAL and degenerate under the capability "
        "transform's log-odds; resolved by the ceiling-anchor convention "
        "(Erik decision 4). INTERIM series pending the METR licence."
    ),
    "status": "verified-ceiling-provisional",
}


def build_workbook() -> None:
    src = pd.read_csv(DUMP_CSV)
    kept = src[src["Environment model"] == ENVIRONMENT].copy()
    excluded = src[src["Environment model"] != ENVIRONMENT]
    measures = pd.DataFrame(
        {
            "parent_name": PARENT,
            "metrics_name": METRIC,
            "papername": PAPERNAME,
            "name": kept["Model version"],
            "date": pd.to_datetime(kept["Release date"]).dt.strftime("%Y-%m-%d"),
            "value": kept["% Resolved"].astype(float) * 100.0,
        }
    ).sort_values("date").reset_index(drop=True)
    metrics = pd.DataFrame(
        [
            {
                "metrics_name": METRIC,
                "parent_name": PARENT,
                "axis_label": "Percentage correct",
                "scale": "Percentage correct",
                "target": 100.0,
                "target_label": "Human-performable ceiling by construction (provisional)",
                "target_source": "arXiv:2412.14161 section 2 (checkpoint design)",
                "protocol": "system_level",
                "chain_year": 2024,
                "source": "Epoch AI (CC BY 4.0), external collection of maintainer results",
                "retrieved": "2026-08-08",
            }
        ]
    )
    with pd.ExcelWriter(OUT_XLSX) as xw:
        measures.to_excel(xw, sheet_name="measures", index=False)
        metrics.to_excel(xw, sheet_name="metrics", index=False)
    print(f"wrote {OUT_XLSX.relative_to(ROOT)}: {len(measures)} observations "
          f"({len(excluded)} other-environment rows excluded), 1 declaration")

    prov = {
        "source": "Epoch AI",
        "url": "https://epoch.ai/data/benchmark_data.zip",
        "licence": "CC BY 4.0",
        "retrieved": "2026-08-08",
        "evaluation": "external",
        "files": {
            "the_agent_company_external.csv": {
                "sha256": hashlib.sha256(DUMP_CSV.read_bytes()).hexdigest(),
                "rows": int(len(src)),
                "rows_kept": int(len(kept)),
            }
        },
        "protocol_note": (
            "OpenHands agent framework throughout (maintainer-run). Series declared as "
            "the Claude-3.5-Sonnet-environment protocol; excluded other-environment "
            f"rows: {[(r['Model version'], str(r['Release date'])) for _, r in excluded.iterrows()]}. "
            "INTERIM pending METR licence (b3: METR primary, SWE-bench secondary)."
        ),
    }
    OUT_PROV.write_text(json.dumps(prov, indent=2))
    print(f"wrote {OUT_PROV.relative_to(ROOT)}")


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
    raw = yaml.safe_load((ROOT / "config-refresh2024.yaml").read_text())
    raw["year_final"] = 2025

    a = _slopes({**raw})
    b = _slopes({**raw, "benchmark_extensions": [str(OUT_XLSX.relative_to(ROOT))]})

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

    ag = b[b["parent_name"] == PARENT]
    print("\nagentic application panel (new, INTERIM):")
    print(ag[["year", "parent_name", "count", "mean"]].to_string(index=False))


if __name__ == "__main__":
    build_workbook()
    append_anchor()
    freeze_history_check()
