#!/usr/bin/env python3
"""Build the provenance sidecar for the measurements recorded from Papers with Code.

WHY THIS EXISTS
---------------
190 of the 2,108 measurements in the frozen benchmark workbook cite
paperswithcode.com. Papers with Code was archived in 2025 and its dumps carry a
CC BY-SA 4.0 licence, so the question for a public release is whether the DAIOE
scores inherit ShareAlike from those rows.

They do not need to, because Papers with Code was a finding aid rather than a
source: 189 of the 190 rows also name the paper in which the measurement was first
published, and all 109 of the rows dated 2020 or later do. What was taken is a
lookup of published facts, not the structure or selection of a database. This file
makes that explicit and checkable, row by row.

WHAT IT DOES NOT DO
-------------------
It does not touch `measures_metrics_newdata2023.xlsx`. That workbook is the frozen
input to the published index, and editing it would risk moving published numbers for
a cosmetic gain. The sidecar sits alongside it.

Output: data/reference/pwc_provenance.csv and a short README beside it.
"""
from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# The 10 Aug 2026 migration removed data/raw/, which duplicated Erik's delivery under
# data_source/. Resolve either, delivery first, so this runs whichever is present.
_CANDIDATES = [
    ROOT / "data_source" / "DAIOE_20260527" / "Data" / "1_data_ore" / "measures_metrics_newdata2023.xlsx",
    ROOT / "data" / "raw" / "measures_metrics_newdata2023.xlsx",
]
SRC = next((c for c in _CANDIDATES if c.exists()), _CANDIDATES[0])
OUT = ROOT / "data" / "reference" / "pwc_provenance.csv"
RESOLVED = Path(sys.argv[1]) if len(sys.argv) > 1 else None


def main():
    x = pd.read_excel(SRC, sheet_name="measures")
    x["year"] = pd.to_datetime(x["date"], errors="coerce").dt.year
    x["from_pwc"] = x["url"].astype(str).str.contains("paperswithcode", case=False)
    p = x[x.from_pwc].copy()

    keep = ["parent_name", "metrics_name", "name", "date", "year", "value",
            "papername", "url"]
    p = p[[c for c in keep if c in p.columns]].rename(columns={
        "parent_name": "application", "metrics_name": "benchmark",
        "name": "model", "papername": "primary_paper",
        "url": "retrieved_from"})

    if RESOLVED and RESOLVED.exists():
        r = pd.read_csv(RESOLVED)
        r = r[r.confidence.isin(["high", "medium"])]
        r["primary_paper"] = r["papername"]
        p = p.merge(r[["primary_paper", "doi", "url", "year", "confidence"]]
                    .rename(columns={"url": "primary_url", "year": "paper_year",
                                     "confidence": "match_confidence"}),
                    on="primary_paper", how="left")
    else:
        for c in ("doi", "primary_url", "paper_year", "match_confidence"):
            p[c] = ""

    p["primary_paper_named"] = p["primary_paper"].notna() & \
        (p["primary_paper"].astype(str).str.strip().str.lower()
         .isin(["", "nan", "no info"]) == False)

    p = p.sort_values(["year", "application", "benchmark"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    p.to_csv(OUT, index=False)

    def filled(col):
        # fillna FIRST: under the Arrow string dtype, astype(str) leaves NaN as NaN
        # rather than the literal "nan", so an isin test silently counts it as filled.
        if col not in p:
            return pd.Series(False, index=p.index)
        s = p[col].fillna("").astype(str).str.strip().str.lower()
        return ~s.isin(["", "nan", "none"])

    named = int(p.primary_paper_named.sum())
    withlink = int((filled("doi") | filled("primary_url")).sum())

    (OUT.parent / "pwc_provenance_README.md").write_text(f"""# Papers with Code provenance

{len(p)} of the 2,108 measurements in the frozen benchmark workbook were recorded from
paperswithcode.com. This file lists every one of them, with the paper in which the
measurement was first published.

- rows: {len(p)}
- naming the primary paper: {named} ({100*named/len(p):.0f} per cent)
- with a resolved DOI or arXiv link: {withlink}

**Why it matters.** Papers with Code is archived and its dumps are CC BY-SA 4.0. Because
each row here is a factual measurement first published elsewhere, and is attributed to
that publication, the DAIOE scores are built from published facts rather than from the
Papers with Code database. `retrieved_from` is retained as an honest record of where we
looked the value up, not as the source of the claim.

**The frozen workbook is unmodified.** This sidecar is generated from it by
`scripts/build_pwc_provenance_20260810.py` and changes no value used by any index.

Column `match_confidence` refers to the automated title-to-DOI match only, never to the
measurement. Rows without a link carry the paper title, which is what the attribution
rests on; the link is a convenience.
""", encoding="utf-8")

    print(f"wrote {OUT}  ({len(p)} rows, {named} naming a primary paper, {withlink} linked)")


if __name__ == "__main__":
    main()
