#!/usr/bin/env python3
"""Rebuild the DAIOE variant series in SSYK space for the AI Unboxed revision (T07/T08).

WHY THIS EXISTS. The 24 Jul build (`build_variants_20260724.py`) harvested the
ISCO-08 panel only, and the resulting `daioe_variants_occ_year.dta` is keyed on
`isco08_4`. The Swedish register build is keyed on SSYK throughout: Mark merges
`daioe_panel_ssyk96.dta` / `daioe_panel_ssyk2012.dta`, and the occupation source
is `ssyk4` (pre-2014) / `ssyk4_2012` (2014 on). Joining ISCO-keyed variants to
SSYK-keyed firm shares would match codes across different classifications, so the
MONA B8 block cannot run until the variants exist in SSYK space. This script
produces them from the same pipeline stages, so the SSYK variants are
pipeline-native rather than crosswalked after the fact.

WHAT IT DOES. Identical construction to 24 Jul: run stages 4-5 under the
social-weight (delta) grid on the frozen config, then harvest per run. The only
change is that it harvests all three taxonomy panels instead of ISCO alone, and
writes one occupation-year file per SSYK vintage.

Outputs (to the mona-batch upload folder):
  - daioe_variants_ssyk2012_year.dta   key `ssyk2012_4` (numeric, as in the panels)
  - daioe_variants_ssyk96_year.dta     key `ssyk96_4`   (numeric)
  - rank-correlation tables per taxonomy, and parquet copies, in the work folder

SELF-CERTIFICATION. The ISCO table is rebuilt too and compared cell-by-cell with
the 24 Jul upload file. If that reproduces exactly, the SSYK tables come from a
run certified identical to the one Erik already verified. If it does not, the
script stops and writes nothing: a silent drift between runs is the one failure
mode that would poison the B8 columns.

`data/out` is backed up before and restored after, so the repo state is
untouched. Baseline = frozen config.yaml (benchmark_updates=[], year_final=2023,
social_weight=2), the construction validated bit-exact against Erik's Stata v1.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "out"
BACKUP = ROOT / "data" / "out_backup_variants_ssyk_tmp"
WORK = ROOT / "data" / "variants_ssyk_20260803"
UPLOAD = Path.home() / "Documents/Workspace/projects/daioe/mona-batch"
REFERENCE_ISCO = UPLOAD / "daioe_variants_occ_year.dta"  # the 24 Jul upload

# social_weight grid: label -> value (baseline delta = 2). Same as 24 Jul.
GRID = {"base": 2, "d05": 0.5, "d1": 1, "d4": 4, "nodw": 1_000_000}

# taxonomy -> (panel file, source key column, output key name, numeric key?)
#
# The SSYK keys are NUMERIC, not zero-padded strings, because that is what the
# register side merges on: Mark destrings the SSYK codes
# (`destring SSYK96kod SSYK2012kod, replace`) and then runs
# `merge m:1 ssyk96_4 year using daioe_panel_ssyk96.dta`. Emitting `ssyk96_4`
# and `ssyk2012_4` exactly as `daioe_panel_ssyk*.dta` carries them means the
# variant files drop into that same merge with no key handling at all.
TAXONOMIES = {
    "isco08":   ("daioe_panel_isco08.dta",   "ISCO08code_str",  "isco08_4",   False),
    "ssyk2012": ("daioe_panel_ssyk2012.dta", "ssyk2012_4",      "ssyk2012_4", True),
    "ssyk96":   ("daioe_panel_ssyk96.dta",   "ssyk96_4",        "ssyk96_4",   True),
}

VARIANT_ORDER = ["d05", "d1", "d4", "nodw"]


def run_pipeline(cfg_path: Path, stages: str = "4,5") -> None:
    cmd = [sys.executable, str(ROOT / "run_all.py"), "--config", str(cfg_path),
           "--stages", stages, "--no-validate"]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:], sep="\n")
        raise RuntimeError(f"pipeline run failed for {cfg_path.name}")


def harvest(tax: str, label: str) -> pd.DataFrame:
    """Pull one taxonomy panel from the current run and rename to variant columns."""
    panel_file, src_key, out_key, numeric_key = TAXONOMIES[tax]
    df = pd.read_stata(OUT / panel_file)
    keep = [src_key, "year", "exp_cumul", "exp_cumul_genai"]
    if label == "base":
        # exp_change is the annual increment; social_skills only drives a sanity
        # check on the no-down-weighting variant.
        keep += ["exp_change", "social_skills"]
    sub = df[keep].copy()
    sub = sub.rename(columns={
        src_key: out_key,
        "exp_cumul": f"daioe_{label}",
        "exp_cumul_genai": f"daioe_genai_{label}",
    })
    if numeric_key:
        sub[out_key] = sub[out_key].astype("float64")
    else:
        # ISCO stays a 4-char zero-padded string, as in the 24 Jul upload
        sub[out_key] = sub[out_key].astype(str).str.strip().str.zfill(4)
    sub["year"] = sub["year"].astype(int)
    return sub


def assemble(tax: str, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Wide occupation-year table for one taxonomy, mirroring the 24 Jul layout."""
    out_key = TAXONOMIES[tax][2]
    wide = frames["base"]
    for label in VARIANT_ORDER:
        wide = wide.merge(
            frames[label][[out_key, "year", f"daioe_{label}"]],
            on=[out_key, "year"], how="inner", validate="one_to_one",
        )
    wide = wide.sort_values([out_key, "year"]).reset_index(drop=True)
    # annual variant = the pipeline's own increment; MA3 = 3-year rolling mean of it
    wide = wide.rename(columns={"exp_change": "daioe_annual"})
    wide["daioe_ma3"] = (
        wide.groupby(out_key)["daioe_annual"]
        .transform(lambda s: s.rolling(3, min_periods=1).mean())
    )
    wide = wide.rename(columns={"daioe_genai_base": "daioe_genai"})
    cols = ([out_key, "year", "daioe_base"] +
            [f"daioe_{v}" for v in VARIANT_ORDER] +
            ["daioe_annual", "daioe_ma3", "daioe_genai", "social_skills"])
    return wide[cols]


def sanity(tax: str, wide: pd.DataFrame) -> pd.DataFrame:
    """Rank correlations, and the behavioural check on the no-down-weighting variant."""
    value_cols = [c for c in wide.columns if c.startswith("daioe_")]
    y23 = wide[wide.year == 2023]
    rc = y23[value_cols].corr(method="spearman")
    print(f"\n[{tax}] Spearman rank correlations with baseline, 2023:")
    print(rc["daioe_base"].round(3).to_string())
    # dropping the social discount must raise exposure most for the most social
    # occupations; if it does not, the delta grid is not doing what it claims
    hi = y23.nlargest(20, "social_skills")
    lo = y23.nsmallest(20, "social_skills")
    lift_hi = (hi.daioe_nodw / hi.daioe_base).mean()
    lift_lo = (lo.daioe_nodw / lo.daioe_base).mean()
    print(f"[{tax}] nodw/base lift: top-20 social {lift_hi:.2f} vs bottom-20 social {lift_lo:.2f}")
    assert lift_hi > lift_lo, f"[{tax}] no-downweight variant does not behave as expected"
    return rc


def certify_isco(rebuilt: pd.DataFrame) -> None:
    """The rebuilt ISCO table must reproduce the 24 Jul upload exactly."""
    if not REFERENCE_ISCO.exists():
        raise RuntimeError(f"reference file missing: {REFERENCE_ISCO}")
    ref = pd.read_stata(REFERENCE_ISCO)
    new = rebuilt.drop(columns=["social_skills"]).copy()
    ref["isco08_4"] = ref["isco08_4"].astype(str).str.strip().str.zfill(4)
    ref["year"] = ref["year"].astype(int)
    ref = ref.sort_values(["isco08_4", "year"]).reset_index(drop=True)
    new = new.sort_values(["isco08_4", "year"]).reset_index(drop=True)
    if list(ref.columns) != list(new.columns):
        raise RuntimeError(f"column mismatch\n ref: {list(ref.columns)}\n new: {list(new.columns)}")
    if len(ref) != len(new):
        raise RuntimeError(f"row count mismatch: reference {len(ref)}, rebuilt {len(new)}")
    if not ref["isco08_4"].equals(new["isco08_4"]) or not ref["year"].equals(new["year"]):
        raise RuntimeError("key mismatch between reference and rebuilt ISCO tables")
    worst = 0.0
    for c in [c for c in new.columns if c.startswith("daioe_")]:
        d = (ref[c].astype("float64") - new[c].astype("float64")).abs().max()
        worst = max(worst, float(d))
    print(f"\nCERTIFICATION vs 24 Jul upload: max|diff| across variant columns = {worst:.3e}")
    # the reference was written as float32 by to_stata, so exact equality is not
    # the right bar; float32 resolution at these magnitudes is ~1e-5
    if worst > 1e-4:
        raise RuntimeError(f"rebuilt ISCO differs from the certified 24 Jul file (max|diff| {worst:.3e})")
    print("CERTIFICATION PASSED: this run reproduces the file Erik verified.")


def main() -> None:
    WORK.mkdir(exist_ok=True)
    UPLOAD.mkdir(exist_ok=True)
    if BACKUP.exists():
        raise RuntimeError("backup dir exists: a previous run did not clean up; inspect first")

    base_cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    assert base_cfg["year_final"] == 2023 and base_cfg["benchmark_updates"] == [], \
        "config.yaml is not the frozen baseline: stop"

    print("backing up data/out ...")
    shutil.copytree(OUT, BACKUP)

    # frames[taxonomy][variant_label]
    frames: dict[str, dict[str, pd.DataFrame]] = {t: {} for t in TAXONOMIES}
    try:
        for label, delta in GRID.items():
            cfg = dict(base_cfg)
            cfg["social_weight"] = delta
            cfg_path = WORK / f"config_variant_{label}.yaml"
            cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
            print(f"running variant {label} (social_weight={delta}, stages 4,5) ...")
            run_pipeline(cfg_path, "4,5")
            for tax in TAXONOMIES:
                frames[tax][label] = harvest(tax, label)
    finally:
        print("restoring data/out from backup ...")
        shutil.rmtree(OUT)
        BACKUP.rename(OUT)

    tables = {tax: assemble(tax, frames[tax]) for tax in TAXONOMIES}
    for tax, wide in tables.items():
        rc = sanity(tax, wide)
        rc.to_csv(WORK / f"rank_correlations_2023_{tax}.csv")

    # certify against the file Erik already verified, before writing anything
    certify_isco(tables["isco08"])

    for tax in ("ssyk2012", "ssyk96"):
        wide = tables[tax].drop(columns=["social_skills"])
        out_dta = UPLOAD / f"daioe_variants_{tax}_year.dta"
        wide.to_stata(out_dta, write_index=False, version=118)
        sz = out_dta.stat().st_size / 1e6
        n_occ = wide[TAXONOMIES[tax][2]].nunique()
        print(f"wrote {out_dta.name}: {len(wide)} rows, {n_occ} occupations, "
              f"{sz:.2f} MB (MONA limit 10 MB: {'OK' if sz < 10 else 'TOO BIG'})")
        wide.to_parquet(WORK / f"daioe_variants_{tax}_year.parquet")
    tables["isco08"].to_parquet(WORK / "daioe_variants_isco08_year.parquet")
    print("done.")


if __name__ == "__main__":
    main()
