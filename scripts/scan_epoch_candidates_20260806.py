"""Scan Epoch AI's benchmark corpus for metrics that could enter DAIOE.

WHY. The frozen basket holds 149 metric series and has thinned badly: four of nine
applications rest on a single benchmark by 2023, and Simple video games retains 2 per cent of
its peak (`notes/FINDING-basket-thinning-2026-08-06.md`). The answer to a thinning basket is
new metrics, not a reweighting of what survives.

SOURCE. `https://epoch.ai/data/benchmark_data.zip`, retrieved 6 Aug 2026. **CC BY 4.0**, which
is the only anchor licence clean enough to carry a redistributed derived index without asking
anyone's permission. Every series is release-dated, which is the property the Hugging Face
route could not supply.

WHAT THIS DOES. Reads every benchmark file, finds its score and date columns, builds an annual
state-of-the-art frontier by running maximum, and reports which series are usable: multi-year,
still rising, and long enough to carry a progress signal. It writes a candidate inventory and
changes nothing in the pipeline.

WHAT IT DOES NOT DO. It does not assign benchmarks to DAIOE applications. That mapping is a
research judgement and belongs to Magnus and Erik; the inventory is the input to it.

Run:  ./.venv/bin/python scripts/scan_epoch_candidates_20260806.py <unzipped_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notes/epoch-candidate-metrics-2026-08-06.csv"

# Columns that are metadata, never the benchmark score.
_META = {
    "training compute (flop)", "training compute notes", "cost per task", "stderr",
    "average standard error", "id", "organization", "country", "model version", "name",
    "notes", "source", "source link", "log viewer", "logs", "started at", "release date",
}


def _score_col(d: pd.DataFrame) -> str | None:
    """The benchmark's headline score. Epoch names it inconsistently, so prefer explicit
    names, then fall back to the first numeric non-metadata column."""
    prefer = ["mean_score", "score", "average progress", "best score (across scorers)",
              "accuracy", "pass@1", "success rate"]
    low = {c.lower(): c for c in d.columns}
    for p in prefer:
        if p in low:
            return low[p]
    for c in d.columns:
        if c.lower() in _META:
            continue
        if pd.api.types.is_numeric_dtype(d[c]) and d[c].notna().sum() >= 5:
            return c
    return None


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not src or not src.exists():
        raise SystemExit("pass the unzipped benchmark_data directory")

    rows = []
    for f in sorted(src.glob("*.csv")):
        try:
            d = pd.read_csv(f, low_memory=False)
        except Exception as e:  # noqa: BLE001
            rows.append({"benchmark": f.stem, "status": f"unreadable: {e}"})
            continue
        dcol = next((c for c in d.columns if c.lower() == "release date"), None)
        scol = _score_col(d)
        if dcol is None or scol is None:
            rows.append({"benchmark": f.stem, "status": "no date or score column"})
            continue
        d[dcol] = pd.to_datetime(d[dcol], errors="coerce", utc=True)
        d = d.dropna(subset=[dcol, scol]).sort_values(dcol)
        if d.empty:
            rows.append({"benchmark": f.stem, "status": "no dated observations"})
            continue
        d["_front"] = pd.to_numeric(d[scol], errors="coerce").cummax()
        yr = d.groupby(d[dcol].dt.year)["_front"].max().dropna()
        if len(yr) < 2:
            rows.append({"benchmark": f.stem, "status": "single year", "n_obs": len(d)})
            continue
        first, last = float(yr.iloc[0]), float(yr.iloc[-1])
        rows.append({
            "benchmark": f.stem.replace("_external", ""),
            "status": "usable",
            "n_obs": len(d),
            "score_col": scol,
            "first_year": int(yr.index[0]),
            "last_year": int(yr.index[-1]),
            "years": len(yr),
            "frontier_first": round(first, 4),
            "frontier_last": round(last, 4),
            "still_rising": bool(yr.iloc[-1] > yr.iloc[:-1].max()) if len(yr) > 1 else False,
            "range": round(last - first, 4),
        })

    t = pd.DataFrame(rows)
    t.to_csv(OUT, index=False)
    ok = t[t.status == "usable"].copy()
    print(f"benchmark files scanned : {len(t)}")
    print(f"usable multi-year series: {len(ok)}")
    live = ok[ok.last_year >= 2025]
    print(f"  of which live in 2025+: {len(live)}")
    print(f"  of which still rising : {int(live.still_rising.sum())}")
    print(f"\nwrote {OUT.relative_to(ROOT)}\n")
    show = live.sort_values(["still_rising", "years", "n_obs"], ascending=False)
    print(show[["benchmark", "n_obs", "first_year", "last_year", "years",
                "frontier_first", "frontier_last", "still_rising"]].head(40).to_string(index=False))


if __name__ == "__main__":
    main()
