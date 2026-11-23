#!/usr/bin/env python3
"""Write the "just the scores" files in scores/: DAIOE in a few columns, for people who want a number.

WHY
---
A user of the ILO generative-AI index found DAIOE too hard to navigate (Nov 2026). The release bundle
carries 51 columns per panel (thirteen applications, legacy and second-generation composites, two
kinds of percentile), across three vintages and five classifications. Most users want one thing: how
exposed is this occupation, now and over time. These files answer that and nothing else.

WHAT
----
From the PUBLISHED v1.1.0 bundle (doi:10.5281/zenodo.22551410), folder vintage-2025, for ISCO-08,
SOC 2010 and SSYK 2012:
  scores/daioe_<tax>_2025.csv   one row per occupation, latest year
  scores/daioe_<tax>_all_years.csv   the same occupations, 2012-2025 (2010-2011 are empty)
Columns: code, title, year, genai (second-generation generative composite daioe_g2gen), genai_pctl,
allai (second-generation all-applications composite daioe_g2all), allai_pctl.

The two measures are the ones the lab's website uses. Percentiles are the tie-safe midrank within
year and classification (pctl_mid_* in the bundle, 0-100, higher = more exposed), copied, not
recomputed. Scores are in standardised units: only their ranking and their changes over time mean
something, not the level.

The script refuses to run if the bundle's SHA256SUMS do not match, so the files cannot drift from the
citable deposit. Run from the repo root:  python3 scripts/build_simple_scores.py
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "dist" / "daioe-v1.1.0-scores"
VINTAGE = "vintage-2025"
OUT = ROOT / "scores"
FIRST_YEAR = 2012  # benchmark coverage starts in 2012; 2010 and 2011 are empty in every panel

# bundle column -> simple column
KEEP = {"daioe_g2gen": "genai", "pctl_mid_g2gen": "genai_pctl",
        "daioe_g2all": "allai", "pctl_mid_g2all": "allai_pctl"}
TAXONOMIES = {"isco08": "ISCO-08", "soc2010": "SOC 2010", "ssyk2012": "SSYK 2012"}


def check_bundle() -> None:
    """Compare every file listed in SHA256SUMS with its hash; stop on any mismatch."""
    for line in (BUNDLE / "SHA256SUMS").read_text().splitlines():
        if not line.strip():
            continue
        digest, name = line.split(maxsplit=1)
        name = name.lstrip("*")
        if name.startswith(VINTAGE) or name == "occupation_titles_ssyk.csv":
            got = hashlib.sha256((BUNDLE / name).read_bytes()).hexdigest()
            if got != digest:
                raise SystemExit(f"checksum mismatch: {name}")


def load(tax: str) -> pd.DataFrame:
    d = pd.read_csv(BUNDLE / VINTAGE / f"daioe_{tax}.tsv", sep="\t", dtype=str)
    if tax == "ssyk2012":
        # the panel stores SSYK numerically (leading zeros lost); titles ship in a separate file
        d["code"] = d["ssyk2012_4"].astype(float).astype(int).astype(str).str.zfill(4) \
            if "ssyk2012_4" in d else d[f"occ_code_{tax}"].str.zfill(4)
        t = pd.read_csv(BUNDLE / "occupation_titles_ssyk.csv", dtype=str)
        d["title"] = d["code"].map(t[t.taxonomy == "ssyk2012"].set_index("code")["title"])
    else:
        d["code"] = d[f"occ_code_{tax}"]
        if tax == "isco08":
            d["code"] = d["code"].str.zfill(4)
        d["title"] = d[f"occ_title_{tax}"]
    d["title"] = d["title"].str.strip()
    # SOC 2010 carries 68 year-less rows with no scores, kept in the bundle for replication
    # (VINTAGES.md, "The exact scope of the freeze guarantee"); they hold nothing to look up
    n_yearless = d["year"].isna().sum()
    if n_yearless:
        print(f"  {tax}: dropping {n_yearless} year-less rows (documented in VINTAGES.md)")
        d = d[d["year"].notna()]
    d["year"] = d["year"].astype(float).astype(int)
    d = d[d.year >= FIRST_YEAR].rename(columns=KEEP)
    for c in KEEP.values():
        d[c] = pd.to_numeric(d[c])
    d = d.dropna(subset=["genai", "allai"], how="all")
    if d["title"].isna().any():
        raise SystemExit(f"{tax}: codes without a title: {sorted(d.loc[d.title.isna(), 'code'].unique())[:10]}")
    d[["genai", "allai"]] = d[["genai", "allai"]].round(4)
    d[["genai_pctl", "allai_pctl"]] = d[["genai_pctl", "allai_pctl"]].round(1)
    return d[["code", "title", "year", *KEEP.values()]].sort_values(["code", "year"])


def main() -> None:
    check_bundle()
    OUT.mkdir(exist_ok=True)
    for tax, label in TAXONOMIES.items():
        d = load(tax)
        last = d.year.max()
        latest = d[d.year == last].sort_values("genai", ascending=False)
        # sanity: one row per occupation and year; percentiles inside 0-100
        assert not d.duplicated(["code", "year"]).any(), tax
        assert d[["genai_pctl", "allai_pctl"]].stack().between(0, 100).all(), tax
        latest.to_csv(OUT / f"daioe_{tax}_{last}.csv", index=False, encoding="utf-8")
        d.to_csv(OUT / f"daioe_{tax}_all_years.csv", index=False, encoding="utf-8")
        top = latest.iloc[0]
        print(f"{label:9s} {latest.shape[0]:4d} occupations, {d.year.min()}-{last}; "
              f"most exposed to generative AI in {last}: {top.code} {top.title}")


if __name__ == "__main__":
    main()
