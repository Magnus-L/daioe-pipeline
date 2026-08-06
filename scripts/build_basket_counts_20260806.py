"""Publish the number of benchmarks behind each application-year.

WHY. Application progress is a mean over whichever metrics have a frontier observation in
that year, and `allapps` sums across applications. So an application whose basket has thinned
to one benchmark enters the composite with the same structural weight as one with eight, and
nothing in the published outputs says so. Four of nine applications rest on a single benchmark
in 2023; Simple video games retains 2 per cent of its peak basket. See
`notes/FINDING-basket-thinning-2026-08-06.md`.

WHAT THIS DOES. Reads the validated frontiers and writes a companion table of counts, plus a
retention summary. It changes no published value. It is the time-dimension analogue of the
`n_soc2010_sources` column on the SOC2018 panel: publish the composition so the reader can see
what stands behind a number.

Run:  ./.venv/bin/python scripts/build_basket_counts_20260806.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daioe import config, io  # noqa: E402

OUT = ROOT / "data/out/application_basket_counts.csv"
OUT_WIDE = ROOT / "data/out/application_basket_counts_wide.csv"


def main() -> None:
    cfg = config.load_config(str(ROOT / "config.yaml"))

    # Prefer the validated reference so the published counts are the published ones; fall
    # back to a rebuild if the reference tree is not mounted.
    ref = cfg.path("enriched_ref") / "metrics_frontiers.dta"
    if ref.exists():
        fr = io.read_dta(str(ref))
        src = "enriched_ref/metrics_frontiers.dta (validated Stata reference)"
    else:
        from daioe import stage2_ai_progress as s2
        measures = s2._build_measures(cfg)
        fr = s2.build_metrics_frontiers(cfg, s2.build_formated_data(cfg), measures)
        src = "rebuilt from source (reference tree not mounted)"
    print(f"source: {src}")

    tidy = (fr.groupby(["parent_name", "year"], as_index=False)["count"]
              .first()
              .rename(columns={"parent_name": "application", "count": "n_benchmarks"}))
    tidy = tidy[tidy["year"].between(cfg.base_year, cfg.year_final)].copy()
    tidy["year"] = tidy["year"].astype(int)
    tidy["n_benchmarks"] = tidy["n_benchmarks"].astype("Int64")

    # the sole contributing benchmark, where there is only one: the fact a reader most needs
    single = fr[fr["year"].between(cfg.base_year, cfg.year_final)].copy()
    single["year"] = single["year"].astype(int)
    solo = (single.groupby(["parent_name", "year"])
                  .filter(lambda g: len(g) == 1)[["parent_name", "year", "metrics_name"]]
                  .rename(columns={"parent_name": "application",
                                   "metrics_name": "sole_benchmark"}))
    tidy = tidy.merge(solo, on=["application", "year"], how="left")

    tidy.to_csv(OUT, index=False)
    wide = tidy.pivot(index="application", columns="year", values="n_benchmarks")
    wide.to_csv(OUT_WIDE)

    peak = wide.max(axis=1)
    last = wide[cfg.year_final]
    summary = pd.DataFrame({"peak": peak, str(cfg.year_final): last,
                            "retained_pct": (100 * last / peak).round(0)})
    print("\nbasket retention, peak to final year:")
    print(summary.sort_values("retained_pct").to_string())
    n_solo = int((last == 1).sum())
    print(f"\napplications on a SINGLE benchmark in {cfg.year_final}: {n_solo} of {len(last)}")
    if n_solo:
        s = tidy[(tidy.year == cfg.year_final) & tidy.sole_benchmark.notna()]
        print(s[["application", "sole_benchmark"]].to_string(index=False))
    print(f"\nwrote {OUT.relative_to(ROOT)} and {OUT_WIDE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
