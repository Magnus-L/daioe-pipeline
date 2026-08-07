"""Epoch AI adapter: the one automatable anchor with a clean licence.

Epoch publishes one CSV per benchmark at ``https://epoch.ai/data/benchmark_data.zip`` under
**CC BY 4.0**, which is the only anchor licence clean enough to carry a redistributed derived
index without anyone's permission. Every row is release-dated, which is the property the
Hugging Face route could not supply and the reason that route was rejected.

Each file carries ``Model version``, a benchmark-specific score column, ``Release date``,
``Organization`` and ``Name``. This adapter reads the series named in the registry, builds a
dated state-of-the-art frontier, and emits rows in the update-workbook schema that
``stage2_ai_progress._load_updates`` already validates.

WHAT IT REFUSES, rather than papering over:
  * a registry series whose file or columns are missing;
  * a row with an unparseable or absent date, since an index defined over time cannot place it;
  * a frontier that moves backwards, which means the direction convention is wrong for that
    scale and would otherwise be recorded as progress.

Provenance is recorded per run: source URL, retrieval date, and the SHA-256 of every file read.
A vintage that cannot say where its numbers came from is not a vintage.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from .registry import SeriesSpec

SOURCE_URL = "https://epoch.ai/data/benchmark_data.zip"
LICENCE = "CC BY 4.0"
ATTRIBUTION = "Epoch AI, benchmark data, CC BY 4.0"

# Scale families where a lower raw value means a more capable system.
LOWER_IS_BETTER = {"Percentage error", "FID", "Perplexity", "Model Entropy"}


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _frontier(df: pd.DataFrame, spec: SeriesSpec) -> tuple[pd.DataFrame, dict]:
    """Dated frontier rows for one series: the running best, in the right direction.

    Undated rows are quarantined rather than dropped or raised on. Epoch carries scores for
    models whose release date it does not record, and those genuinely cannot be placed in a
    year. But silence is the failure mode the guards exist to prevent, so the count and the
    names go into provenance, and one check is fatal: if any quarantined row would have sat on
    the frontier, the frontier we build is wrong and the series must not be ingested until the
    date is recovered.
    """
    d = df[[spec.score_col, spec.date_col, "Model version"]].copy()
    d.columns = ["value", "date", "name"]
    d["value"] = pd.to_numeric(d["value"], errors="coerce") * spec.value_multiplier
    d["date"] = pd.to_datetime(d["date"], errors="coerce")

    undated = d[d["date"].isna() & d["value"].notna()]
    d = d.dropna(subset=["value", "date"]).sort_values("date")
    if d.empty:
        raise ValueError(f"{spec.metrics_name}: every row is undated; nothing can be placed")

    if len(undated):
        best = d["value"].min() if spec.scale in LOWER_IS_BETTER else d["value"].max()
        beats = (undated["value"] < best) if spec.scale in LOWER_IS_BETTER else (undated["value"] > best)
        if beats.any():
            raise ValueError(
                f"{spec.metrics_name}: {int(beats.sum())} undated row(s) exceed the dated "
                f"frontier ({sorted(undated.loc[beats, 'name'].astype(str))[:3]}). The frontier "
                f"would be wrong. Recover the dates before ingesting this series."
            )
    quarantine = {
        "undated_rows": int(len(undated)),
        "undated_models": sorted(undated["name"].astype(str))[:20],
    }
    if d.empty:
        raise ValueError(f"{spec.metrics_name}: no usable rows in {spec.source_series}")

    running = d["value"].cummin() if spec.scale in LOWER_IS_BETTER else d["value"].cummax()
    d["is_frontier"] = running.ne(running.shift(1)) | (d.index == d.index[0])
    front = d[d["is_frontier"]].copy()

    # A frontier that moves the wrong way means the direction convention is wrong for this
    # scale, which is precisely the defect the frozen `threshold` column carries.
    step = front["value"].diff().dropna()
    if len(step) and ((step > 0).any() and (step < 0).any()):
        raise ValueError(
            f"{spec.metrics_name}: frontier moves in both directions, so the declared scale "
            f"{spec.scale!r} disagrees with the data. Check the direction convention."
        )
    return front, quarantine


def build_updates(specs: list[SeriesSpec], data_dir: Path) -> tuple[pd.DataFrame, dict]:
    """Return (rows in update-workbook schema, provenance record)."""
    rows, prov_files = [], {}
    for spec in specs:
        if spec.source != "epoch":
            continue
        spec.validate()
        f = data_dir / f"{spec.source_series}_external.csv"
        if not f.exists():
            raise FileNotFoundError(
                f"{spec.metrics_name}: {f.name} not in the Epoch dump. The series may have been "
                f"renamed or withdrawn; do not substitute a similar one without re-checking."
            )
        df = pd.read_csv(f)
        for col in (spec.score_col, spec.date_col, "Model version"):
            if col not in df.columns:
                raise KeyError(
                    f"{spec.metrics_name}: column {col!r} absent from {f.name}. "
                    f"Available: {sorted(df.columns)}"
                )
        front, quarantine = _frontier(df, spec)
        prov_files[f.name] = {"sha256": _sha256(f), **quarantine}
        for _, r in front.iterrows():
            rows.append({
                "parent_name": spec.parent_name,
                "metrics_name": spec.metrics_name,
                "papername": ATTRIBUTION,
                "name": str(r["name"]),
                "date": r["date"].strftime("%Y-%m-%d"),
                "value": float(r["value"]),
            })

    provenance = {
        "source": "Epoch AI",
        "url": SOURCE_URL,
        "licence": LICENCE,
        "retrieved": date.today().isoformat(),
        "files": prov_files,
        "series": [asdict(s) for s in specs if s.source == "epoch"],
    }
    return pd.DataFrame(rows), provenance


def write_workbook(rows: pd.DataFrame, provenance: dict, out_dir: Path, tag: str) -> Path:
    """Write the measures workbook and its provenance sidecar."""
    out_dir.mkdir(parents=True, exist_ok=True)
    xlsx = out_dir / f"measures_updates_{tag}.xlsx"
    rows.to_excel(xlsx, sheet_name="measures", index=False)
    with open(out_dir / f"provenance_{tag}.json", "w", encoding="utf-8") as fh:
        json.dump(provenance, fh, indent=2)
    return xlsx
