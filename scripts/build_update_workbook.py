"""Build the Track A update workbook: PwC-archive rows extending the frozen basket.

Phase A4 of the Phase 2 plan. For every usable metric in the verified crosswalk
(notes/track-a-crosswalk.csv, statuses matched-confirmed and matched-continuation),
extract dump rows dated strictly after that metric's last date in the frozen
workbook and map them to the frozen measures schema. The stage-2 machinery
computes the SOTA frontier itself (running max in date order), so below-frontier
rows are harmless and everything after the cutoff is emitted.

Rules locked by the A2 audit (notes/track-a-coverage-audit.md):
- statuses frozen / frozen-duplicate / ambiguous-excluded / refuted / unmatched
  contribute nothing; the news-test-2014 duplicates are carried by their canonical
  WMT2014 siblings, SQuAD by nothing.
- transforms convert dump units into the frozen rows' units:
  ImageNet top-5   ours = (100 - dump)/100   (dump stores accuracy %, frozen stores
                                              error fraction; stage 2 rescales later)
  MSVD-QA          ours = dump * 100         (dump stores 0-1 fraction)
- zero-evidence metrics (no frozen measures rows) take every dated dump row.

Output: data/updates/measures_updates_2024plus.xlsx, single sheet "measures",
columns exactly as the frozen sheet: parent_name_cleaned, parent_name,
metrics_name, name, date, value, papername, url. Loader guards in
src/daioe/stage2_ai_progress.py validate on ingest.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = ROOT / "notes" / "track-a-crosswalk.csv"
FLAT = ROOT / "data" / "updates" / "pwc-archive" / "flat_sota.parquet"
RAW_XLSX = ROOT / "data" / "raw" / "measures_metrics_newdata2023.xlsx"
OUT = ROOT / "data" / "updates" / "measures_updates_2024plus.xlsx"

TRANSFORMS = {
    "Imagenet Image Recognition": lambda v: (100.0 - v) / 100.0,
    "MSVD-QA": lambda v: v * 100.0,
}


def main() -> None:
    cw = pd.read_csv(CROSSWALK)
    usable = cw[cw.status.str.startswith(("matched-confirmed", "matched-continuation"))]
    print(f"usable metrics: {len(usable)} of {len(cw)}")

    flat = pd.read_parquet(FLAT)
    flat["date"] = pd.to_datetime(flat["paper_date"], errors="coerce")

    frozen = pd.read_excel(RAW_XLSX, sheet_name="measures")
    frozen["date"] = pd.to_datetime(frozen["date"], errors="coerce")
    last_date = frozen.groupby("metrics_name")["date"].max()
    # parent_name -> parent_name_cleaned is one-to-one in the frozen sheet
    cleaned = frozen.drop_duplicates("parent_name").set_index("parent_name")[
        "parent_name_cleaned"
    ]

    out_frames = []
    for _, r in usable.iterrows():
        sub = flat[
            (flat.benchmark == r.benchmark)
            & (flat.metric_col == r.metric_col)
            & flat.date.notna()
            & flat.value_float.notna()
        ]
        cutoff = last_date.get(r.metrics_name)
        if pd.notna(cutoff):
            sub = sub[sub.date > cutoff]
        if sub.empty:
            continue
        val = sub.value_float
        if r.metrics_name in TRANSFORMS:
            val = val.map(TRANSFORMS[r.metrics_name])
        out_frames.append(
            pd.DataFrame(
                {
                    "parent_name_cleaned": cleaned[r.parent_name],
                    "parent_name": r.parent_name,
                    "metrics_name": r.metrics_name,
                    "name": sub.model_name.values,
                    "date": sub.date.values,
                    "value": val.values,
                    "papername": sub.paper_title.values,
                    "url": sub.paper_url.values,
                }
            )
        )

    upd = pd.concat(out_frames, ignore_index=True)
    upd = upd.drop_duplicates(["metrics_name", "name", "date", "value"])
    upd = upd.sort_values(["parent_name", "metrics_name", "date"]).reset_index(drop=True)

    with pd.ExcelWriter(OUT) as xw:
        upd.to_excel(xw, sheet_name="measures", index=False)

    print(f"update rows: {len(upd)} across {upd.metrics_name.nunique()} metrics")
    print(f"date range: {upd.date.min().date()} .. {upd.date.max().date()}")
    by_year = upd.date.dt.year.value_counts().sort_index()
    print("rows per year:", dict(by_year))
    print("\nrows per application:")
    print(upd.groupby("parent_name").size().sort_values(ascending=False).to_string())
    print(f"\n-> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
