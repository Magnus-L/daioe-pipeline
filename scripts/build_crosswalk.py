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


def flatten_dump() -> pd.DataFrame:
    """Walk the nested sota-extractor structure into one row per (benchmark, metric, model).

    Streams per parquet row group (pyarrow) and frees each chunk: the nested structures
    explode in memory as Python objects, so whole-file pandas loading OOMs.
    """
    import gc

    import pyarrow.parquet as pq

    records: list[tuple] = []

    def walk(t: dict) -> None:
        task = t.get("task") or ""
        for ds in t.get("datasets") or []:
            dataset = ds.get("dataset") or ""
            bench = f"{task} on {dataset}"
            sota = ds.get("sota") or {}
            for row in sota.get("rows") or []:
                model = row.get("model_name") or ""
                date = str(row.get("paper_date") or "")
                metrics = row.get("metrics") or {}
                items = metrics.items() if isinstance(metrics, dict) else [
                    (m.get("key"), m.get("value")) for m in metrics
                ]
                for mcol, val in items:
                    records.append(
                        (bench, task, dataset, str(mcol), model, date, str(val), parse_value(val))
                    )
        for st in t.get("subtasks") or []:
            walk(st)

    for f in sorted(glob.glob(str(DUMP_DIR / "evaluation-tables-train-*.parquet"))):
        pf = pq.ParquetFile(f)
        for rg in range(pf.num_row_groups):
            chunk = pf.read_row_group(rg).to_pylist()
            for t in chunk:
                walk(t)
            del chunk
            gc.collect()
    cols = ["benchmark", "task", "dataset", "metric_col", "model_name",
            "paper_date", "value_str", "value_float"]
    return pd.DataFrame.from_records(records, columns=cols)


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
    if FLAT_OUT.exists():
        flat = pd.read_parquet(FLAT_OUT)
        print(f"loaded cached flat dump: {len(flat):,} rows")
    else:
        flat = flatten_dump()
        flat.to_parquet(FLAT_OUT, index=False)
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
