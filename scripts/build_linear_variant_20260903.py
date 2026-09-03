"""Add a LINEAR (non-squared) DAIOE variant to the SSYK variant panels.

Sarah Schroeder, AI Unboxed co-author meeting 3 Sep 2026 (comment C3): equation
(5) squares the exposure increment, and the paper asserts the non-linearity
rather than showing the specification without it. Erik's stated reason on the
record is that without the square the between-occupation variation is narrow and
the index is dominated by the time dimension. That reason belongs in the paper,
next to an estimate that does not use the square.

WHAT THIS DOES
    Eq. (5) is  DAIOE_ot = ( De_ot * w_o )^p , cumulated over years.  The
    published build has p = 2. This script runs the pipeline once more with
    p = 1, everything else identical, and appends the result as `daioe_lin` to
    the two SSYK variant panels the register side actually merges on.

WHY BOTH SSYK VINTAGES
    About 79 per cent of firm baseline occupation rows are SSYK96-coded, because
    baseline is the firm's first observed year and most firms enter before the
    2014 classification change. An ISCO-keyed or SSYK2012-only file would cover
    a fifth of the sample and say nothing about it. 6_robustness.do section 6.9
    reads both panels by name and refuses the ISCO file for this reason.

CERTIFICATION, which is the point of the script
    The exponent is a new config option defaulting to 2, so every existing config
    is unchanged. This script proves that by rebuilding the BASE variant through
    the patched code and comparing it cell for cell with the stored panel. If
    that check fails, nothing is written.

OUTPUT
    data/variants_ssyk_20260903/daioe_variants_ssyk96_year.dta
    data/variants_ssyk_20260903/daioe_variants_ssyk2012_year.dta
    each = the 3 Aug panel plus one new column, `daioe_lin`.
"""
from __future__ import annotations
import shutil, subprocess, sys
from pathlib import Path
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "out"
PREV = ROOT / "data" / "variants_ssyk_20260803"
WORK = ROOT / "data" / "variants_ssyk_20260903"
BACKUP = ROOT / "data" / "out_backup_linear_tmp"

TAX = {  # tax -> (panel file, source key, output key)
    "ssyk2012": ("daioe_panel_ssyk2012.dta", "ssyk2012_4", "ssyk2012_4"),
    "ssyk96":   ("daioe_panel_ssyk96.dta",   "ssyk96_4",   "ssyk96_4"),
}


def run_pipeline(cfg: Path) -> None:
    r = subprocess.run([sys.executable, str(ROOT / "run_all.py"), "--config", str(cfg),
                        "--stages", "4,5", "--no-validate"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:], sep="\n")
        raise RuntimeError(f"pipeline failed for {cfg.name}")


def harvest(tax: str, colname: str) -> pd.DataFrame:
    panel_file, src_key, out_key = TAX[tax]
    df = pd.read_stata(OUT / panel_file)[[src_key, "year", "exp_cumul"]].copy()
    df = df.rename(columns={src_key: out_key, "exp_cumul": colname})
    df[out_key] = df[out_key].astype("float64")
    df["year"] = df["year"].astype(int)
    return df


def main() -> int:
    WORK.mkdir(exist_ok=True)
    if BACKUP.exists():
        shutil.rmtree(BACKUP)
    shutil.copytree(OUT, BACKUP)
    print(f"data/out backed up to {BACKUP.name}")

    # the 3 Aug builder derives every variant from the MAIN config and overrides one
    # key; the stored config_variant_*.yaml files carry no paths: block and cannot
    # be run on their own.
    base_cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    try:
        # ---- 1. CERTIFY: rebuild base through the patched code ----
        cfg_b = dict(base_cfg)
        cfg_b.pop("exponent", None)          # absent, so the default of 2 is exercised
        p = WORK / "config_certify_base.yaml"
        p.write_text(yaml.safe_dump(cfg_b, sort_keys=False))
        print("certifying: rebuilding the BASE variant through the patched stage 4 ...")
        run_pipeline(p)
        ok = True
        for tax in TAX:
            got = harvest(tax, "daioe_base")
            want = pd.read_parquet(PREV / f"daioe_variants_{tax}_year.parquet")[
                [TAX[tax][2], "year", "daioe_base"]]
            m = want.merge(got, on=[TAX[tax][2], "year"], how="outer",
                           suffixes=("_stored", "_rebuilt"), indicator=True)
            unmatched = int((m["_merge"] != "both").sum())
            both = m[m["_merge"] == "both"]
            diff = (both["daioe_base_stored"] - both["daioe_base_rebuilt"]).abs()
            nz = int((diff.fillna(0) > 0).sum())
            print(f"  {tax}: rows {len(m)}, unmatched {unmatched}, "
                  f"cells differing {nz}, max |d| {float(diff.max() or 0):.3e}")
            if unmatched or nz:
                ok = False
        if not ok:
            print("\nCERTIFICATION FAILED. The exponent patch is not behaviour-preserving.")
            print("Nothing written. Do not upload anything from this run.")
            return 1
        print("  certification PASSED: base reproduces bit for bit.\n")

        # ---- 2. BUILD: the linear variant ----
        cfg_l = dict(base_cfg)
        cfg_l["exponent"] = 1
        p = WORK / "config_variant_lin.yaml"
        p.write_text(yaml.safe_dump(cfg_l, sort_keys=False))
        print("building the LINEAR variant (exponent 1) ...")
        run_pipeline(p)
        for tax in TAX:
            lin = harvest(tax, "daioe_lin")
            prev = pd.read_parquet(PREV / f"daioe_variants_{tax}_year.parquet")
            wide = prev.merge(lin, on=[TAX[tax][2], "year"], how="left")
            miss = int(wide["daioe_lin"].isna().sum()) - int(prev["daioe_base"].isna().sum())
            r = wide[["daioe_base", "daioe_lin"]].dropna().corr().iloc[0, 1]
            print(f"  {tax}: rows {len(wide)}, extra missing {miss}, "
                  f"corr(base, lin) = {r:.4f}")
            wide.to_stata(WORK / f"daioe_variants_{tax}_year.dta",
                          write_index=False, version=117)
            wide.to_parquet(WORK / f"daioe_variants_{tax}_year.parquet", index=False)
        print(f"\nwritten to {WORK}")
        return 0
    finally:
        shutil.rmtree(OUT)
        shutil.copytree(BACKUP, OUT)
        shutil.rmtree(BACKUP)
        print("data/out restored from backup")


if __name__ == "__main__":
    raise SystemExit(main())
