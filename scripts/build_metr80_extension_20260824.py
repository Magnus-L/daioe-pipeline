"""Build the METR 80%-reliability agentic workbook: the successor bar, decided 24 Aug 2026.

WHY THIS EXISTS. Magnus decided on 24 Aug 2026 to switch the agentic series to the
80%-reliability horizon. The trigger is measured, not speculative: in Epoch's 24 Aug
corpus the 50%-reliability frontier reads 1,044.78 minutes (claude-mythos-preview-early,
2026-04-07), ABOVE the suite's own 960-minute reliability boundary, with a second model at
718.8. The 2025 vintage is untouched (its 50% frontier is 352 against 960), but the next
vintage would inherit an exhausted instrument mid-window. The pre-declared response to an
instrument ceiling was always a re-declared series, and this is that series: the SAME
pinned suite (METR-Horizon-v1.1, same tasks, same source file, same permission) at a
stricter reliability bar, whose frontier currently tops out around 186 minutes, far from
the bound.

THE DOUBLE-COUNT RULE, inherited from the 13 Aug builder verbatim: p50 and p80 are the
same construct at two reliability levels, so the two series must NEVER be in the basket
together; the assembler's --agentic flag selects exactly one. This workbook REPLACES the
50% one when selected, it never joins it.

Everything else mirrors the 13 Aug admission: METR-Horizon-v1.1 pin asserted against the
file's own benchmark_name; v1.0 excluded entirely (construct drift: the same model reads
differently under the two harnesses); observations before the 2024 chain year dropped
(guard 6; nothing informative is lost, the pre-2024 p80 maximum is far below the 2024
frontier); central estimates above the 960-minute suite bound excluded by the same rule
installed on the 50% series (none currently qualify on the 80% bar, which is the point of
the switch). Scale 'Score' (ln minutes), protocol system_level, anchor 960.0
instrument-ceiling PROVISIONAL pending the ceiling-anchor convention.

Outputs mirror every admission: workbook + provenance sidecar + anchor row + freeze-history
check (must print 0.00e+00), plus the 50%-vs-80% panel comparison for the meeting.
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

SRC_DIR = ROOT / "data" / "updates" / "metr_20260813"
SRC_YAML = SRC_DIR / "benchmark_results_1_1.yaml"
OUT_XLSX = ROOT / "data" / "updates" / "extension_metr80_2026-08-24.xlsx"
OUT_PROV = ROOT / "data" / "updates" / "provenance_metr80_2026-08-24.json"
ANCHORS = ROOT / "data" / "derived" / "human_anchors_v1.csv"

PARENT = "Agentic task execution"
METRIC = "Agentic task horizon at 80% reliability on METR-Horizon"
P50_METRIC = "Agentic task horizon at 50% reliability on METR-Horizon"
P50_XLSX = ROOT / "data" / "updates" / "extension_metr_2026-08-13.xlsx"

VERSION = "METR-Horizon-v1.1"
CHAIN_YEAR = 2024
CEILING_MIN = 960.0  # the suite's own reliability boundary, unchanged by the bar
PAPERNAME = ("METR task-horizon evaluations (metr.org), benchmark_results_1_1.yaml, "
             "80% reliability; used with permission, 2026-08-13")

ANCHOR_ROW = {
    "metrics_name": METRIC,
    "parent_name": PARENT,
    "scale": "Score",
    "anchor": CEILING_MIN,
    "anchor_kind": "instrument-ceiling",
    "category": "B",
    "source": "METR, benchmark_results_1_1.yaml and metr.org/time-horizons (retrieved 2026-08-13)",
    "evidence": (
        "Same suite and bound as the 50% series: the horizon axis is denominated in "
        "human-expert time, so no human-parity value exists; the suite's declared "
        "reliability boundary is 16 hours (960 minutes). The 80% bar is the successor "
        "series adopted 24 Aug 2026 after the 50% frontier crossed the bound in the 2026 "
        "data (1,044.78 min, 2026-04-07); its own frontier (~186 min) has ample headroom. "
        "p50 and p80 are one construct at two reliability levels and are never in the "
        "basket together. PROVISIONAL pending the ceiling-anchor convention."
    ),
    "status": "verified-ceiling-provisional",
}


def _load_results(path: Path, field: str) -> pd.DataFrame:
    doc = yaml.safe_load(path.read_text())
    rows = []
    for name, m in doc["results"].items():
        p = m["metrics"][field]
        rows.append(
            {
                "name": name,
                "date": pd.to_datetime(m["release_date"]).strftime("%Y-%m-%d"),
                "value": float(p["estimate"]),
                "ci_low": float(p["ci_low"]),
                "ci_high": float(p["ci_high"]),
            }
        )
    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    df.attrs["doc"] = doc
    return df


def build_workbook() -> None:
    src = _load_results(SRC_YAML, "p80_horizon_length")
    doc = src.attrs["doc"]
    assert doc["benchmark_name"] == VERSION, f"expected {VERSION}, got {doc['benchmark_name']}"

    year = pd.to_datetime(src["date"]).dt.year
    pre_chain = src[year < CHAIN_YEAR]
    above_ceiling = src[(year >= CHAIN_YEAR) & (src["value"] > CEILING_MIN)]
    kept = src[(year >= CHAIN_YEAR) & (src["value"] <= CEILING_MIN)].copy()

    measures = pd.DataFrame(
        {
            "parent_name": PARENT,
            "metrics_name": METRIC,
            "papername": PAPERNAME,
            "name": kept["name"],
            "date": kept["date"],
            "value": kept["value"],
        }
    ).reset_index(drop=True)
    metrics = pd.DataFrame(
        [
            {
                "metrics_name": METRIC,
                "parent_name": PARENT,
                "axis_label": "Task length completed at 80% reliability (human-expert minutes)",
                "scale": "Score",
                "target": CEILING_MIN,
                "target_label": "Suite reliability ceiling, 16 h (provisional)",
                "target_source": "METR benchmark_results_1_1.yaml doubling-time note; metr.org/time-horizons",
                "protocol": "system_level",
                "chain_year": CHAIN_YEAR,
                "source": f"METR {VERSION}, used with permission 2026-08-13",
                "retrieved": "2026-08-24",
            }
        ]
    )
    with pd.ExcelWriter(OUT_XLSX) as xw:
        measures.to_excel(xw, sheet_name="measures", index=False)
        metrics.to_excel(xw, sheet_name="metrics", index=False)
    print(f"wrote {OUT_XLSX.relative_to(ROOT)}: {len(measures)} observations "
          f"({len(pre_chain)} pre-chain-year, {len(above_ceiling)} above-ceiling excluded), "
          f"1 declaration")

    prov = {
        "source": "METR",
        "url": "https://metr.org/assets/benchmark_results_1_1.yaml",
        "page": "https://metr.org/time-horizons/",
        "field": "p80_horizon_length",
        "licence": None,
        "licence_basis": (
            "Written permission granted to the AI-Econ Lab by Wilder Seitz (METR) on "
            "2026-08-13 to derive occupation-year values and redistribute them in the "
            "public index. Conditions: cite METR; never indicate a partnership. See "
            "notes/PERMISSION-metr_2026-08-13.md. METR agreed 18 Aug to add CC BY 4.0; "
            "check scripts/check_metr_licence.py at release time."
        ),
        "retrieved": "2026-08-24",
        "evaluation": "metr-published",
        "files": {
            SRC_YAML.name: {
                "sha256": hashlib.sha256(SRC_YAML.read_bytes()).hexdigest(),
                "rows": int(len(src)),
            }
        },
        "succession_note": (
            "Successor bar to the 50% series, decided 24 Aug 2026 after the 50% frontier "
            "crossed the 960-minute suite bound in 2026 data (1,044.78 min). Same construct, "
            "stricter reliability; the two are never in the basket together."
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
    print(f"anchor row appended ({len(anchors)} anchors)")


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
    print(f"freeze-history: {len(wa)} application-years, "
          f"max |d progress| = {dmean:.2e}, max |d basket count| = {dcount:.0f}")
    if dmean != 0.0 or dcount != 0.0:
        raise SystemExit("FREEZE-HISTORY VIOLATION: the extension changed published values")

    print("\nagentic panel on the 80% bar:")
    print(b[b["parent_name"] == PARENT][["year", "count", "mean"]].to_string(index=False))

    c = _slopes({**raw, "benchmark_extensions": [str(P50_XLSX.relative_to(ROOT))]})
    print("\nagentic panel on the 50% bar (for comparison):")
    print(c[c["parent_name"] == PARENT][["year", "count", "mean"]].to_string(index=False))


if __name__ == "__main__":
    build_workbook()
    append_anchor()
    freeze_history_check()
