"""Refresh-mode validation report (Phase 2 Track A).

The standard per-stage validation hard-gates on row counts, which a refresh run
legitimately violates twice over: new years exist, and appending post-2023 data
resurrects span rows INSIDE 2010-2023 (each metric's panel is trimmed to its
observed year span, so a 2024 result for a dormant metric adds zero-rows for the
gap years, changing application-year mean denominators). This report therefore
compares by KEYED OUTER JOIN on the year <= slice_year slice and reports three
things per target instead of pass/fail:

  1. value drift on common keys (max |got - ref| per column, cells > tol);
  2. got-only keys inside the slice (the resurrection channel, quantified);
  3. ref-only keys inside the slice (must be ZERO: losing rows is always a bug).

Plus new-year consistency checks on years > slice_year.

Usage:
  python run_all.py --config config-refresh2024.yaml --stages 2,4,5 --no-validate
  python scripts/refresh_report.py [--config config-refresh2024.yaml] [--slice-year 2023]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daioe import io  # noqa: E402
from daioe.config import load_config  # noqa: E402

# (name, got file under out/, ref resolver, ref file, keys)
TARGETS = [
    ("s2 slopes allapps", "slopes_slimmed_allapps.parquet", "enriched_ref", "slopes_slimmed_allapps.dta", ["application", "year"]),
    ("s2 slopes genai", "slopes_slimmed_genai.parquet", "enriched_ref", "slopes_slimmed_genai.dta", ["application", "year"]),
    ("s2 slopes lngmod", "slopes_slimmed_lngmod.parquet", "enriched_ref", "slopes_slimmed_lngmod.dta", ["application", "year"]),
    ("s2 metrics_frontiers", "metrics_frontiers.parquet", "enriched_ref", "metrics_frontiers.dta", ["metrics_name", "year"]),
    ("s4 onet preliminary", "daioe_panel_onet_preliminary.parquet", "enriched_ref", "daioe_panel_onet_preliminary.dta", ["occ_code_onet", "year"]),
    ("s5 onet", "daioe_panel_onet.dta", "reference", "daioe_panel_onet.dta", ["occ_code_onet", "year"]),
    ("s5 soc", "daioe_panel_soc.dta", "reference", "daioe_panel_soc.dta", ["occ_code_soc", "year"]),
    ("s5 isco08", "daioe_panel_isco08.dta", "reference", "daioe_panel_isco08.dta", ["ISCO08code", "year"]),
    ("s5 ssyk2012", "daioe_panel_ssyk2012.dta", "reference", "daioe_panel_ssyk2012.dta", ["ssyk2012_4", "year"]),
    ("s5 ssyk96", "daioe_panel_ssyk96.dta", "reference", "daioe_panel_ssyk96.dta", ["ssyk96_4", "year"]),
]


def load_any(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.suffix == ".parquet" else io.read_dta(path)


def compare_slice(name, got, ref, keys, slice_year, tol):
    """Keyed outer-join comparison on the year <= slice_year slice."""
    lines = [f"### {name}"]
    g = got[got["year"] <= slice_year].copy()
    r = ref[ref["year"] <= slice_year].copy()
    for k in keys:
        g[k] = g[k].astype(str) if g[k].dtype == object else g[k]
        r[k] = r[k].astype(str) if r[k].dtype == object else r[k]
    m = g.merge(r, on=keys, how="outer", suffixes=("_got", "_ref"), indicator=True)
    n_gonly = int((m["_merge"] == "left_only").sum())
    n_ronly = int((m["_merge"] == "right_only").sum())
    lines.append(f"- rows (slice): got {len(g)}, ref {len(r)}; got-only {n_gonly}, ref-only {n_ronly}"
                 + ("  ⚠ REF-ONLY ROWS = BUG" if n_ronly else ""))
    both = m[m["_merge"] == "both"]
    val_cols = sorted(
        c[:-4] for c in m.columns if c.endswith("_got")
        and f"{c[:-4]}_ref" in m.columns
        and pd.api.types.is_numeric_dtype(m[c])
        and not c[:-4].startswith("pctl_rank")
    )
    drifted = []
    for c in val_cols:
        a, b = both[f"{c}_got"].astype(float), both[f"{c}_ref"].astype(float)
        nan_mismatch = int((a.isna() != b.isna()).sum())
        d = (a - b).abs()
        mx = float(d.max()) if d.notna().any() else 0.0
        n_over = int((d > tol).sum())
        if n_over or nan_mismatch:
            drifted.append((c, mx, n_over, nan_mismatch))
    if drifted:
        lines.append(f"- {len(drifted)}/{len(val_cols)} columns drift beyond tol={tol}:")
        for c, mx, n_over, nanm in sorted(drifted, key=lambda x: -x[1])[:12]:
            lines.append(f"    - `{c}`: max|diff| {mx:.3e}, cells>tol {n_over}"
                         + (f", NaN-mask mismatches {nanm}" if nanm else ""))
    else:
        lines.append(f"- all {len(val_cols)} shared value columns within tol={tol} on common keys")
    return "\n".join(lines), n_gonly, n_ronly, drifted


def newyear_checks(name, got, keys, slice_year):
    lines = [f"### {name} (years > {slice_year})"]
    ny = got[got["year"] > slice_year]
    if not len(ny):
        lines.append("- no new-year rows")
        return "\n".join(lines)
    lines.append(f"- rows: {len(ny)}, years: {sorted(ny['year'].unique())}")
    num = [c for c in ny.columns if pd.api.types.is_numeric_dtype(ny[c]) and c not in keys]
    nan_cols = {c: int(ny[c].isna().sum()) for c in num if ny[c].isna().any()}
    lines.append(f"- NaNs in new-year numeric cells: {nan_cols if nan_cols else 'none'}")
    if "mean" in ny.columns:
        neg = int((ny["mean"] < 0).sum())
        lines.append(f"- negative progress means: {neg}" + ("  ⚠" if neg else ""))
    cumul = [c for c in ny.columns if c.startswith("exp_cumul")]
    if cumul and len(keys) == 2:
        ent = keys[0]
        bad = 0
        full = got.sort_values([ent, "year"])
        for c in cumul:
            d = full.groupby(ent)[c].diff()
            bad += int((d[full["year"] > slice_year] < -1e-9).sum())
        lines.append(f"- cumulative-column decreases in new years: {bad}" + ("  ⚠" if bad else ""))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config-refresh2024.yaml"))
    ap.add_argument("--slice-year", type=int, default=2023)
    args = ap.parse_args()
    cfg = load_config(args.config)
    tol = cfg.tol_internal

    parts = [f"# Refresh-mode report — {datetime.now():%Y-%m-%d %H:%M}",
             f"config: `{args.config}` · slice year: {args.slice_year} · tol: {tol}",
             "",
             "## Slice comparison (years <= slice year) vs frozen targets"]
    summary = []
    for name, got_name, res, ref_name, keys in TARGETS:
        got_path = cfg.out_file(got_name)
        ref_path = cfg.reference_file(ref_name) if res == "reference" else cfg.enriched_ref_file(ref_name)
        if not got_path.exists():
            parts.append(f"### {name}\n- SKIPPED (missing {got_path.name})")
            continue
        got, ref = load_any(got_path), load_any(ref_path)
        block, n_gonly, n_ronly, drifted = compare_slice(name, got, ref, keys, args.slice_year, tol)
        parts.append(block)
        summary.append((name, n_gonly, n_ronly, len(drifted)))
    parts.append("\n## New-year consistency checks")
    for name, got_name, res, ref_name, keys in TARGETS:
        got_path = cfg.out_file(got_name)
        if got_path.exists():
            parts.append(newyear_checks(name, load_any(got_path), keys, args.slice_year))

    parts.append("\n## Summary (seam quantification inputs)")
    parts.append("| target | got-only keys in slice | ref-only (bug if >0) | drifting cols |")
    parts.append("|---|---|---|---|")
    for name, g, r, d in summary:
        parts.append(f"| {name} | {g} | {r} | {d} |")

    out = cfg.path("reports") / f"refresh_{datetime.now():%Y%m%d_%H%M%S}.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"report -> {out}")
    for name, g, r, d in summary:
        print(f"  {name}: got-only {g}, ref-only {r}, drifting cols {d}")


if __name__ == "__main__":
    main()
