"""Build the software-engineering extension workbook: SWE-bench Verified, chained 2024.

Answers Magnus's question of 8 Aug 2026 ("and what about SWE-bench -- cannot we use it?"):
yes, today, and this script does it. The licence obstacle the charter recorded applies to
the swebench.com LEADERBOARD (CC BY-NC, self-reported entries, only a third independently
checked). Epoch runs SWE-bench Verified in its own harness and redistributes the results
under CC BY 4.0, which is on the registry's clean-licence list; the b3 subdomain-evidence
note had already reached this verdict. The parent application needs no new machinery:
"Write computer programs from specifications" is frozen application id 4, never in
`allapps`, exactly like conversation before today.

Series design:

* SOURCE: `swe_bench_verified.csv` from Epoch's benchmark_data.zip -- an Epoch-RUN file
  (no `_external` suffix), so one known evaluation protocol: "a fairly simple prompt,
  close to that used in the SWE-bench developers' bash-only runs", 484 of 500 samples
  validated on their infrastructure. 35 model rows, releases 2024-11 to 2026-06, frontier
  31.0 -> 83.5 per cent. All observations post-chain, so guard 6 is satisfied without
  excluding anything.

* PROTOCOL: system_level -- the model plus its scaffold (bash, editor, patch tools) is the
  measured object, as the benchmark's own definition says a firm would deploy it. This is
  the measure's first system-level series; it must never be mixed with pure_model rows.

* ANCHOR: 95.0, human-ceiling, PROVISIONAL pending the anchor convention (Erik decision 4).
  Every task is a real GitHub issue that a human engineer actually resolved (the merged PR
  is ground truth), and the Verified subset was triple-annotated by 93 software developers
  as well-specified; by construction the human reference is the ceiling. Epoch: "some
  samples may remain ambiguous -- and we have previously estimated an error rate of 5-10%",
  so a flawless agent is bounded below 100 by residual sample defects; 95.0 is the
  conservative reading (100 minus the lower bound), the same convention the anchors file
  applies to HellaSwag. A ceiling anchor is degenerate under the capability transform's
  log-odds (an anchor of 100 clips to ~13.8 log-odds); at 95.0 theta is finite and modest,
  and the FID-floor result applies: anchor error costs information weight, not measured
  progress.

* DATES: model release dates, as carried in Epoch's own `Release date` column -- the GPQA
  convention. Two models carry two scorer rows each (claude-opus-4-6, gpt-5.1); both rows
  are kept, and the frontier's running max resolves them.

Outputs:
  data/updates/extension_swebench_2026-08-08.xlsx   (measures + metrics sheets)
  data/updates/provenance_swebench_2026-08-08.json  (source file sha256, licence, quotes)
  an anchor row appended to data/derived/human_anchors_v1.csv (idempotent)
  freeze-history check printed (must be 0.00e+00 over the published window)
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

DUMP_CSV = ROOT / "data" / "updates" / "epoch_dump_20260808" / "swe_bench_verified.csv"
OUT_XLSX = ROOT / "data" / "updates" / "extension_swebench_2026-08-08.xlsx"
OUT_PROV = ROOT / "data" / "updates" / "provenance_swebench_2026-08-08.json"
ANCHORS = ROOT / "data" / "derived" / "human_anchors_v1.csv"

PARENT = "Write computer programs from specifications"
METRIC = "Software issue resolution on SWE-bench Verified"
PAPERNAME = "Epoch AI, benchmark data, CC BY 4.0 (Epoch-run harness, 484 of 500 samples)"

ANCHOR_ROW = {
    "metrics_name": METRIC,
    "parent_name": PARENT,
    "scale": "Percentage correct",
    "anchor": 95.0,
    "anchor_kind": "human-ceiling",
    "category": "B",
    "source": "epoch.ai/benchmarks/swe-bench-verified (retrieved 2026-08-08)",
    "evidence": (
        '"a human-validated subset of the original SWE-bench dataset, consisting of 500 '
        'samples"; "curated through a rigorous human annotation process involving 93 software '
        'developers. Each sample was reviewed by three separate annotators"; "Nevertheless, '
        'some samples may remain ambiguous - and we have previously estimated an error rate '
        'of 5-10%". Ceiling by construction (every task is a human-resolved GitHub issue); '
        "95.0 = 100 minus the lower bound of the residual error estimate, conservative "
        "reading per the HellaSwag convention. PROVISIONAL pending the ceiling-anchor "
        "convention (Erik decision 4)."
    ),
    "status": "verified-ceiling-provisional",
}


def build_workbook() -> None:
    src = pd.read_csv(DUMP_CSV)
    measures = pd.DataFrame(
        {
            "parent_name": PARENT,
            "metrics_name": METRIC,
            "papername": PAPERNAME,
            "name": src["Model version"],
            "date": pd.to_datetime(src["Release date"]).dt.strftime("%Y-%m-%d"),
            "value": src["mean_score"].astype(float) * 100.0,
        }
    ).sort_values("date").reset_index(drop=True)
    metrics = pd.DataFrame(
        [
            {
                "metrics_name": METRIC,
                "parent_name": PARENT,
                "axis_label": "Percentage correct",
                "scale": "Percentage correct",
                "target": 95.0,
                "target_label": "Human-resolved ceiling, conservative reading (provisional)",
                "target_source": "epoch.ai/benchmarks/swe-bench-verified",
                "protocol": "system_level",
                "chain_year": 2024,
                "source": "Epoch AI (CC BY 4.0), Epoch-run harness",
                "retrieved": "2026-08-08",
            }
        ]
    )
    with pd.ExcelWriter(OUT_XLSX) as xw:
        measures.to_excel(xw, sheet_name="measures", index=False)
        metrics.to_excel(xw, sheet_name="metrics", index=False)
    print(f"wrote {OUT_XLSX.relative_to(ROOT)}: {len(measures)} observations, 1 declaration")

    prov = {
        "source": "Epoch AI",
        "url": "https://epoch.ai/data/benchmark_data.zip",
        "licence": "CC BY 4.0",
        "retrieved": "2026-08-08",
        "evaluation": "epoch-run",
        "files": {
            "swe_bench_verified.csv": {
                "sha256": hashlib.sha256(DUMP_CSV.read_bytes()).hexdigest(),
                "rows": int(len(src)),
            }
        },
        "protocol_note": (
            "Epoch-run harness: 'a fairly simple prompt, close to that used in the SWE-bench "
            "developers' bash-only runs'; 484 of 500 samples validated on their infrastructure; "
            "tools: bash, text editor, patch application."
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
    """Same pattern as the ToMBench admission: both runs at year_final 2025, differing
    only in this workbook; the published 2010-2023 window must be bit-identical."""
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

    sw = b[b["parent_name"] == PARENT]
    print("\nsoftware engineering application panel (new):")
    print(sw[["year", "parent_name", "count", "mean"]].to_string(index=False))


if __name__ == "__main__":
    build_workbook()
    append_anchor()
    freeze_history_check()
