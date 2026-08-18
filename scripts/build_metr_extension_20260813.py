"""Build the PRIMARY agentic extension workbook: METR task horizons, chained 2024.

METR granted written permission on 13 Aug 2026 (notes/PERMISSION-metr_2026-08-13.md),
which closes the only thing that stood between this series and the index. It now becomes
the primary agentic anchor exactly as the B3 subdomain-evidence note designed, with
TheAgentCompany (interim, shipped in v2025) demoted to corroboration or retired at the
next chain point, and SWE-bench Verified the benchmark-grounded companion.

Why METR, and why it was worth waiting for: it is the only source found in the B1 scan
that treats agentic capability as an explicit, protocol-declared, dated series, and its
metric is the one a labour economist would have asked for if given the choice. The unit is
human-expert MINUTES: the length of task, measured by how long human experts took, that a
model completes with 50% reliability. That is a capability measured in the currency of
work, not in points on a benchmark.

SOURCE. `https://metr.org/assets/benchmark_results_1_1.yaml`, METR's own published results
file, the one behind the download button on metr.org/time-horizons/. A primary artefact,
not a scrape of the rendered page, per the B1 hallucination-hazard rule. Copied into
data/updates/metr_20260813/ and hashed, so the build reproduces from a local file.

VERSION PIN. METR publishes two constructs, v1.0 and v1.1, and they are NOT the same
measurement: gpt_4 reads 6.024 minutes under v1.0 and 3.987 under v1.1, because v1.1
re-runs the suite under Inspect. Mixing them would book a harness change as capability.
This series is DECLARED as METR-Horizon-v1.1, pinned by the benchmark's own content hashes
(long_tasks_version, swaa_version) rather than by a date, and v1.0 is excluded entirely.
v1.1 is the current construct and runs later (to 2026-04 against v1.0's 2025-11).

METRIC. p50_horizon_length, the 50%-reliability horizon in minutes. The p80 series exists
in the same file and is not used: it is the same construct at a stricter reliability, so
including both would double-count one measurement.

SCALE. 'Score' -> ln(v). This is the correct family rather than a convenience: METR's own
analysis is log-linear in minutes (they report a DOUBLING TIME), so a constant increment
of ln(minutes) is exactly one doubling of the work a run can absorb. The transform and the
source's own construct agree, which is not true of every series in the basket.

ANCHOR. 960.0 minutes (16 hours), anchor_kind 'instrument-ceiling', PROVISIONAL. This is a
NEW anchor kind and it is deliberate. Every other anchor in the basket is a score a human
achieves, so 'value >= target' reads as human parity. Here the axis is ALREADY denominated
in human-expert time, so there is no horizon at which the human stops: what stops is the
instrument. METR declares the boundary itself, in this file's own comment on the doubling
time, "excludes points with central estimate p50 > 16 hrs", and on the page as
"measurements above 16 hrs are unreliable on this task suite". Crossing it is therefore not
a parity event but an exhausted instrument, and the honest response at the next chain point
is a re-declared or replaced suite, not a threshold. Flagged for the ceiling-anchor
convention (Erik decision 4), which now has three distinct ceiling cases to unify:
SWE-bench (95.0, residual-error discounted), TheAgentCompany (100.0, undiscounted), and
this one.

EXCLUSIONS, each a declared rule rather than a judgement call, all recorded in provenance:
  1. v1.0 in full (construct drift, above);
  2. observations before the 2024 chain year, which the admission door forbids (guard 6).
     They change nothing: the pre-2024 maximum is 4.045 minutes against a 2024 frontier of
     38.832, so the baseline is identical whether or not they are carried;
  3. central estimates above the 960-minute ceiling, following METR's own trend-fit rule.
     One row qualifies, claude_mythos_preview_early_inspect at 1044.78 on 2026-04-07, which
     is outside the v2025 window in any case. The rule is installed now so that the next
     vintage does not have to invent it under pressure.

Outputs mirror the SWE-bench and TheAgentCompany admissions: workbook + provenance sidecar
+ anchor row + freeze-history check (must print 0.00e+00), plus a comparison of the agentic
panel under both series, which is the first half of the METR-vs-TheAgentCompany agreement
check (ISSUES-and-ideas, improvement idea 2).
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
OUT_XLSX = ROOT / "data" / "updates" / "extension_metr_2026-08-13.xlsx"
OUT_PROV = ROOT / "data" / "updates" / "provenance_metr_2026-08-13.json"
ANCHORS = ROOT / "data" / "derived" / "human_anchors_v1.csv"

PARENT = "Agentic task execution"
METRIC = "Agentic task horizon at 50% reliability on METR-Horizon"
INTERIM_METRIC = "Agentic work-task resolution on TheAgentCompany"
INTERIM_XLSX = ROOT / "data" / "updates" / "extension_agentcompany_2026-08-08.xlsx"

VERSION = "METR-Horizon-v1.1"
CHAIN_YEAR = 2024
CEILING_MIN = 960.0  # 16 hours, METR's own declared reliability boundary
PAPERNAME = ("METR task-horizon evaluations (metr.org), benchmark_results_1_1.yaml; "
             "used with permission, 2026-08-13")

ANCHOR_ROW = {
    "metrics_name": METRIC,
    "parent_name": PARENT,
    "scale": "Score",
    "anchor": CEILING_MIN,
    "anchor_kind": "instrument-ceiling",
    "category": "B",
    "source": "METR, benchmark_results_1_1.yaml and metr.org/time-horizons (retrieved 2026-08-13)",
    "evidence": (
        "The horizon axis is denominated in human-expert time, so no human-parity value "
        "exists on it; what bounds the series is the suite. METR declares that bound "
        'itself: the results file computes its doubling time "excludes points with central '
        'estimate p50 > 16 hrs", and the page states that measurements above 16 hrs are '
        "unreliable on this task suite. 960.0 minutes is that boundary. Crossing it means "
        "the instrument is exhausted, not that parity was reached, so the response is a "
        "re-declared or replaced suite at the next chain point. NEW anchor kind "
        "(instrument-ceiling); PROVISIONAL pending the ceiling-anchor convention "
        "(Erik decision 4)."
    ),
    "status": "verified-ceiling-provisional",
}


def _load_results(path: Path) -> pd.DataFrame:
    """One row per evaluated model: date, name, p50 horizon in minutes, with CI."""
    doc = yaml.safe_load(path.read_text())
    rows = []
    for name, m in doc["results"].items():
        p50 = m["metrics"]["p50_horizon_length"]
        rows.append(
            {
                "name": name,
                "date": pd.to_datetime(m["release_date"]).strftime("%Y-%m-%d"),
                "value": float(p50["estimate"]),
                "ci_low": float(p50["ci_low"]),
                "ci_high": float(p50["ci_high"]),
            }
        )
    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    df.attrs["doc"] = doc
    return df


def build_workbook() -> dict:
    src = _load_results(SRC_YAML)
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
                "axis_label": "Task length completed at 50% reliability (human-expert minutes)",
                "scale": "Score",
                "target": CEILING_MIN,
                "target_label": "Suite reliability ceiling, 16 h (provisional)",
                "target_source": "METR benchmark_results_1_1.yaml doubling-time note; metr.org/time-horizons",
                "protocol": "system_level",
                "chain_year": CHAIN_YEAR,
                "source": f"METR {VERSION}, used with permission 2026-08-13",
                "retrieved": "2026-08-13",
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
        "licence": None,
        "licence_basis": (
            "No licence file exists on METR/eval-analysis-public. Written permission granted "
            "to the AI-Econ Lab by Wilder Seitz (METR) on 2026-08-13, in reply to the request "
            "of 2026-08-07, to derive occupation-year values and redistribute them as part of "
            "the public index. Conditions: cite METR; never indicate a partnership. The "
            "permission was granted to us and does not travel with the data. See "
            "notes/PERMISSION-metr_2026-08-13.md."
        ),
        "attribution_required": (
            "Agentic task-horizon series derived from METR's public evaluation data "
            "(metr.org), used with permission. METR is not affiliated with this work and "
            "does not endorse it."
        ),
        "retrieved": "2026-08-13",
        "evaluation": "external",
        "version_pin": {
            "benchmark_name": doc["benchmark_name"],
            "long_tasks_version": doc["long_tasks_version"],
            "doubling_time_in_days": doc["doubling_time_in_days"],
        },
        "files": {
            p.name: {
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "bytes": p.stat().st_size,
            }
            for p in sorted(SRC_DIR.glob("*.yaml"))
        },
        "metric_note": (
            "p50_horizon_length (minutes at 50% reliability). The p80 series in the same file "
            "is the same construct at a stricter reliability and is not used, to avoid "
            "double-counting one measurement."
        ),
        "protocol_note": (
            f"System-level by construct (the scaffold is the object). Declared as {VERSION}; "
            "v1.0 excluded in full, since it is a different construct (gpt_4 reads 6.024 min "
            "under v1.0 and 3.987 under v1.1, an Inspect re-run, not a capability change). "
            "Excluded pre-chain-year rows: "
            f"{[(r['name'], r['date'], round(r['value'], 3)) for _, r in pre_chain.iterrows()]}. "
            f"Excluded above the {CEILING_MIN:.0f}-minute suite ceiling, following METR's own "
            "trend-fit rule: "
            f"{[(r['name'], r['date'], round(r['value'], 3)) for _, r in above_ceiling.iterrows()]}."
        ),
        "supersedes": (
            "TheAgentCompany (extension_agentcompany_2026-08-08.xlsx) was the INTERIM agentic "
            "series pending this permission. Demotion to corroboration or retirement is a "
            "chain-point decision, recorded either way; this workbook does not remove it."
        ),
    }
    OUT_PROV.write_text(json.dumps(prov, indent=2))
    print(f"wrote {OUT_PROV.relative_to(ROOT)}")
    return {"kept": kept, "pre_chain": pre_chain, "above_ceiling": above_ceiling}


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
    ext = str(OUT_XLSX.relative_to(ROOT))
    interim = str(INTERIM_XLSX.relative_to(ROOT))

    a = _slopes({**raw})
    b = _slopes({**raw, "benchmark_extensions": [ext]})

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

    # Does the new series behave like its own scale family? A Score-family series produces
    # systematically larger increments than a Percentage-correct one (median 0.372 against
    # 0.141), so the basket is the wrong comparison and the family is the right one.
    from daioe import scale_family_check as sfc
    cfg_b = cfgmod.Config(raw={**raw, "benchmark_extensions": [ext]}, root=ROOT)
    meas_b = s2._build_measures(cfg_b)
    fd_b = s2.build_formated_data(cfg_b)
    fr_b = s2.build_metrics_frontiers(cfg_b, fd_b, meas_b)
    print()
    print(sfc.check_series(fr_b, fd_b, METRIC).summary())

    print(f"\nagentic application panel, METR ({VERSION}) as the series:")
    print(b[b["parent_name"] == PARENT][["year", "count", "mean"]].to_string(index=False))

    # The agreement check's first half: the same application under the interim series, and
    # under both at once. Two independent instruments for one construct is the designed
    # answer to the "the increase is purely mechanical" critique.
    c = _slopes({**raw, "benchmark_extensions": [interim]})
    d = _slopes({**raw, "benchmark_extensions": [ext, interim]})
    print(f"\nagentic application panel, TheAgentCompany (interim) as the series:")
    print(c[c["parent_name"] == PARENT][["year", "count", "mean"]].to_string(index=False))
    print(f"\nagentic application panel, both series in the basket:")
    print(d[d["parent_name"] == PARENT][["year", "count", "mean"]].to_string(index=False))

    # Commensurability: the 2025 increment of every application, so the new series can be
    # read against the basket it joins rather than on its own.
    print("\n2025 increment by application, METR in the basket:")
    y25 = b[(b["year"] == 2025) & (b["parent_name"] != "robotics")]
    print(y25[["parent_name", "count", "mean"]].sort_values("mean", ascending=False)
          .to_string(index=False))


if __name__ == "__main__":
    build_workbook()
    append_anchor()
    freeze_history_check()
