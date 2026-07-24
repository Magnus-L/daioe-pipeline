#!/usr/bin/env python3
"""Build DAIOE variant series for the AI Unboxed revision (T07/T08).

Runs the validated pipeline (stages 4-5) under a social-weight (delta) grid,
harvests the ISCO-08 internal panel per run, derives annual and MA3 variants
from the baseline, and writes:

  - mona-batch upload file: daioe_variants_occ_year.dta  (occ x year, wide)
  - rank-correlation table (2023) across variants        (for the T06 appendix)
  - a run log with sanity checks

Provenance rules: baseline = frozen config.yaml (benchmark_updates=[],
year_final=2023, social_weight=2), the exact construction validated bit-exact
against Erik's Stata v1. Variants differ ONLY in social_weight. data/out is
backed up before and restored after, so the repo state (2024-refresh) is
untouched. Drafted for Erik's verification, 2026-07-24.
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
BACKUP = ROOT / "data" / "out_backup_variants_tmp"
WORK = ROOT / "data" / "variants_20260724"
UPLOAD = Path.home() / "Documents/Workspace/projects/daioe/mona-batch"
PANEL = OUT / "daioe_panel_isco08.dta"

# social_weight grid: label -> value (baseline delta = 2)
GRID = {"base": 2, "d05": 0.5, "d1": 1, "d4": 4, "nodw": 1_000_000}


def run_pipeline(cfg_path: Path, stages: str = "4,5") -> None:
    cmd = [sys.executable, str(ROOT / "run_all.py"), "--config", str(cfg_path),
           "--stages", stages, "--no-validate"]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:], sep="\n")
        raise RuntimeError(f"pipeline run failed for {cfg_path.name}")


def main() -> None:
    WORK.mkdir(exist_ok=True)
    UPLOAD.mkdir(exist_ok=True)
    if BACKUP.exists():
        raise RuntimeError("backup dir exists — previous run did not clean up; inspect first")
    print("backing up data/out ...")
    shutil.copytree(OUT, BACKUP)

    base_cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    assert base_cfg["year_final"] == 2023 and base_cfg["benchmark_updates"] == [], \
        "config.yaml is not the frozen baseline — stop"

    frames: dict[str, pd.DataFrame] = {}
    try:
        for i, (label, delta) in enumerate(GRID.items()):
            cfg = dict(base_cfg)
            cfg["social_weight"] = delta
            cfg_path = WORK / f"config_variant_{label}.yaml"
            cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
            # data/out holds 2024-refresh checkpoints; the FIRST run must rebuild
            # stages 1-3 under the frozen config so stage 4 sees matching inputs.
            stages = "4,5"  # checkpoints now FROZEN (restored raw, certified bit-exact 24 Jul eve)
            print(f"running variant {label} (social_weight={delta}, stages {stages}) ...")
            run_pipeline(cfg_path, stages)
            df = pd.read_stata(PANEL)
            keep = ["ISCO08code_str", "year", "exp_cumul", "exp_cumul_genai"]
            if label == "base":
                keep += ["exp_change", "social_skills"]
            sub = df[keep].copy()
            ren = {"exp_cumul": f"daioe_{label}", "exp_cumul_genai": f"daioe_genai_{label}"}
            sub = sub.rename(columns=ren)
            frames[label] = sub
            sub.to_parquet(WORK / f"panel_{label}.parquet")
    finally:
        print("restoring data/out from backup ...")
        shutil.rmtree(OUT)
        BACKUP.rename(OUT)

    # ---- assemble wide occupation-year table ----
    wide = frames["base"]
    for label in ("d05", "d1", "d4", "nodw"):
        wide = wide.merge(
            frames[label][["ISCO08code_str", "year", f"daioe_{label}"]],
            on=["ISCO08code_str", "year"], how="inner", validate="one_to_one",
        )
    wide = wide.sort_values(["ISCO08code_str", "year"]).reset_index(drop=True)
    # annual variant = the pipeline's own increment; MA3 = 3-year rolling mean of it
    wide = wide.rename(columns={"exp_change": "daioe_annual"})
    wide["daioe_ma3"] = (
        wide.groupby("ISCO08code_str")["daioe_annual"]
        .transform(lambda s: s.rolling(3, min_periods=1).mean())
    )
    wide = wide.rename(columns={"ISCO08code_str": "isco08_4", "daioe_genai_base": "daioe_genai"})
    genai_keep = ["daioe_genai"]
    cols = (["isco08_4", "year", "daioe_base"] +
            [f"daioe_{v}" for v in ("d05", "d1", "d4", "nodw")] +
            ["daioe_annual", "daioe_ma3"] + genai_keep + ["social_skills"])
    wide = wide[cols]

    # ---- sanity checks ----
    y23 = wide[wide.year == 2023]
    rc = y23[[c for c in cols if c.startswith("daioe_")]].corr(method="spearman")
    print("\nSpearman rank correlations, 2023:\n", rc.round(3).to_string())
    # nodw must raise exposure most for the most social occupations
    hi_soc = y23.nlargest(20, "social_skills")
    lo_soc = y23.nsmallest(20, "social_skills")
    lift_hi = (hi_soc.daioe_nodw / hi_soc.daioe_base).mean()
    lift_lo = (lo_soc.daioe_nodw / lo_soc.daioe_base).mean()
    print(f"\nnodw/base lift: top-20 social {lift_hi:.2f} vs bottom-20 social {lift_lo:.2f}")
    assert lift_hi > lift_lo, "no-downweight variant does not behave as expected"

    # ---- write deliverables ----
    rc.to_csv(WORK / "rank_correlations_2023.csv")
    out_dta = UPLOAD / "daioe_variants_occ_year.dta"
    wide.drop(columns=["social_skills"]).to_stata(out_dta, write_index=False, version=118)
    sz = out_dta.stat().st_size / 1e6
    print(f"\nwrote {out_dta} ({sz:.2f} MB, {len(wide)} rows) — MONA limit 10 MB: {'OK' if sz < 10 else 'TOO BIG'}")
    wide.to_parquet(WORK / "daioe_variants_occ_year.parquet")
    print("done.")


if __name__ == "__main__":
    main()
