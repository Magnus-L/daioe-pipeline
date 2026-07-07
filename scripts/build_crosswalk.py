"""Build the Track A crosswalk: our 149 metric rows -> PwC (task, dataset, metric column).

Strategy (Phase A2 of the Phase 2 plan). Erik's 2023 workbook rows were hand-taken from
Papers With Code, so for a correct match the dump's (model_name, value) pairs must overlap
the frozen measures rows for that metric. We therefore score every candidate
(benchmark, metric_column) in the dump by how many of our frozen (name, value) pairs it
reproduces. Value-overlap evidence is decisive; name similarity is only a tie-breaker.

Outputs
-------
data/updates/pwc-archive/flat_sota.parquet   flattened dump (one row per benchmark x metric x model)
notes/track-a-crosswalk-draft.csv            top-3 candidates per metric with evidence scores

The draft is then adversarially verified (agents + review) before becoming
notes/track-a-crosswalk.csv, the committed deliverable.
"""

from __future__ import annotations

import glob
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DUMP_DIR = ROOT / "data" / "updates" / "pwc-archive"
RAW_XLSX = ROOT / "data" / "raw" / "measures_metrics_newdata2023.xlsx"
FLAT_OUT = DUMP_DIR / "flat_sota.parquet"
DRAFT_OUT = ROOT / "notes" / "track-a-crosswalk-draft.csv"


def parse_value(s: str) -> float:
    """Parse a PwC metric value string to float (strip %, commas, spaces); NaN if not numeric."""
    if s is None:
        return np.nan
    t = str(s).strip().replace("%", "").replace(",", "").replace(" ", "")
    # tolerate scores like "0.912(0.003)" by taking the leading number
    m = re.match(r"^[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", t)
    return float(m.group(0)) if m else np.nan


COLS = ["benchmark", "task", "dataset", "metric_col", "model_name",
        "paper_date", "value_str", "value_float"]


def flatten_dump() -> pd.DataFrame:
    """Walk the nested sota-extractor structure into one row per (benchmark, metric, model).

    Two traps in the HF parquet conversion of the sota-extractor JSON (established
    2026-07-07 after this job froze the machine; see memory note):

    1. THE trap: `metrics` was a per-row dict with arbitrary keys in the source JSON;
       parquet requires a fixed schema, so the converter unioned ALL metric names in
       the dump into one giant struct. Every row decodes with ~3,200 keys, nearly all
       null. Emitting them without a null-skip yields ~500M records (52 GB) instead
       of ~500k. Skip null/empty values; never take len(metrics) at face value.
    2. Minor: the same subtask subtree can be embedded under several parents (PwC's
       task graph is a DAG); dedupe on task name so each is walked once.

    Materialise ONE top-level row at a time: whole-shard to_pylist decodes the full
    null-padded struct for every row simultaneously and OOMs a 16 GB machine.

    Validation targets (deduplicated; see notes/track-a-provenance.md): 3,976 unique
    tasks, 76,227 unique SOTA rows. (The A1 probe's 6,449 / 155,456 were walk counts
    including embedded duplicates.) The record and memory valves abort if output
    explodes, so a regression here can never re-freeze the machine.
    """
    import csv
    import resource

    import pyarrow.parquet as pq

    MAX_RECORDS = 5_000_000  # ~10x the expected ~500k; explosion tripwire
    MAX_RSS_GB = 8  # abort before the 16 GB machine starts paging
    tmp_csv = FLAT_OUT.with_suffix(".csv.tmp")
    records: list[tuple] = []
    seen_tasks: set[str] = set()
    n_sota_rows = 0

    def walk(t: dict) -> None:
        nonlocal n_sota_rows
        task = t.get("task") or ""
        if task in seen_tasks:  # identical embedded copy — already fully walked
            return
        seen_tasks.add(task)
        for ds in t.get("datasets") or []:
            dataset = ds.get("dataset") or ""
            bench = f"{task} on {dataset}"
            sota = ds.get("sota") or {}
            for row in sota.get("rows") or []:
                n_sota_rows += 1
                model = row.get("model_name") or ""
                date = str(row.get("paper_date") or "")
                metrics = row.get("metrics") or {}
                items = metrics.items() if isinstance(metrics, dict) else [
                    (m.get("key"), m.get("value")) for m in metrics
                ]
                for mcol, val in items:
                    if val is None or val == "":  # null-padded union-struct fields
                        continue
                    records.append(
                        (bench, task, dataset, str(mcol), model, date, str(val), parse_value(val))
                    )
        for st in t.get("subtasks") or []:
            walk(st)

    with open(tmp_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLS)
        n_flushed = 0
        for f in sorted(glob.glob(str(DUMP_DIR / "evaluation-tables-train-*.parquet"))):
            pf = pq.ParquetFile(f)
            for rg in range(pf.num_row_groups):
                table = pf.read_row_group(rg)
                for i in range(table.num_rows):
                    walk(table.slice(i, 1).to_pylist()[0])
                    if len(records) >= 100_000:
                        n_flushed += len(records)
                        if n_flushed > MAX_RECORDS:
                            raise RuntimeError(
                                f"record valve tripped at {n_flushed:,} records; "
                                "dedup is not holding — aborting before disk/RAM damage"
                            )
                        writer.writerows(records)
                        records.clear()
                    if i % 100 == 0:
                        rss_gb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9
                        print(f"  {Path(f).name}: row {i}/{table.num_rows}, "
                              f"{len(seen_tasks):,} tasks, {n_sota_rows:,} sota rows, "
                              f"peak {rss_gb:.1f} GB", flush=True)
                        if rss_gb > MAX_RSS_GB:
                            raise RuntimeError(
                                f"memory valve tripped at {rss_gb:.1f} GB peak — aborting"
                            )
                del table
            print(f"  flattened {Path(f).name} "
                  f"(cum: {len(seen_tasks):,} tasks, {n_sota_rows:,} sota rows)", flush=True)
        writer.writerows(records)
        records.clear()

    print(f"walk totals: {len(seen_tasks):,} unique tasks, {n_sota_rows:,} sota rows "
          f"(expect 3,976 / 76,227 deduplicated)", flush=True)

    flat = pd.read_csv(tmp_csv, dtype={"value_str": str}, keep_default_na=False,
                       na_values=[], low_memory=False)
    flat["value_float"] = pd.to_numeric(flat["value_float"], errors="coerce")
    flat.to_parquet(FLAT_OUT, index=False)
    tmp_csv.unlink()
    return flat


def norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def values_close(a: float, b: float) -> bool:
    if np.isnan(a) or np.isnan(b):
        return False
    if a == b:
        return True
    denom = max(abs(a), abs(b), 1e-12)
    return abs(a - b) / denom < 1e-3


def main() -> None:
    # hard memory ceiling: a runaway allocation gets a MemoryError, not a frozen machine
    import resource
    try:
        resource.setrlimit(resource.RLIMIT_DATA, (10 * 1024**3, 10 * 1024**3))
    except (ValueError, OSError):
        pass  # not enforceable on this platform; the soft valves still apply

    if FLAT_OUT.exists():
        flat = pd.read_parquet(FLAT_OUT)
        print(f"loaded cached flat dump: {len(flat):,} rows")
    else:
        flat = flatten_dump()
        print(f"flattened dump: {len(flat):,} rows -> {FLAT_OUT.name}")

    ours_metrics = pd.read_excel(RAW_XLSX, sheet_name="metrics")
    ours_measures = pd.read_excel(RAW_XLSX, sheet_name="measures")
    ours_measures["value_float"] = pd.to_numeric(ours_measures["value"], errors="coerce")

    # evidence sets per metric: (normalised model name -> values)
    evidence: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for _, r in ours_measures.iterrows():
        evidence[r["metrics_name"]].append((norm_name(r["name"]), r["value_float"]))

    # index dump by normalised model name for fast lookup
    flat["model_norm"] = flat["model_name"].map(norm_name)
    by_model = flat.groupby("model_norm", sort=False)

    rows_out = []
    for _, mrow in ours_metrics.iterrows():
        mname, app = mrow["metrics_name"], mrow["parent_name"]
        ev = evidence.get(mname, [])
        # score candidates: for each frozen (model, value), find dump rows with same
        # model whose value matches; tally per (benchmark, metric_col)
        scores: dict[tuple[str, str], int] = defaultdict(int)
        for model_n, val in ev:
            if not model_n or model_n not in by_model.groups:
                continue
            cand = by_model.get_group(model_n)
            hit = cand[[values_close(val, v) for v in cand["value_float"]]]
            for key in set(zip(hit["benchmark"], hit["metric_col"])):
                scores[key] += 1
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])[:3]
        exact = f"{mname}" in set(flat["benchmark"])  # exact PwC-style name
        base = {
            "metrics_name": mname,
            "parent_name": app,
            "scale": mrow.get("scale"),
            "n_evidence_rows": len(ev),
            "exact_name_in_dump": exact,
        }
        for rank, ((bench, mcol), sc) in enumerate(ranked, start=1):
            base[f"cand{rank}"] = f"{bench} | {mcol}"
            base[f"cand{rank}_hits"] = sc
        rows_out.append(base)

    draft = pd.DataFrame(rows_out)
    draft.to_csv(DRAFT_OUT, index=False)
    matched = draft["cand1_hits"].notna() & (draft["cand1_hits"] > 0)
    strong = matched & (draft["cand1_hits"] >= 3)
    print(f"metrics with any value-overlap candidate: {int(matched.sum())}/{len(draft)}")
    print(f"strong (>=3 overlapping rows):            {int(strong.sum())}/{len(draft)}")
    print(f"draft -> {DRAFT_OUT}")


if __name__ == "__main__":
    main()
