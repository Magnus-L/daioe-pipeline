"""Round-trip verification of the SOC2018 crosswalk, against the BLS original.

The 4 August verification ran on the O*NET-derived crosswalk and reported
max|diff| = 0.000e+00 across 13 exp_change_* columns on 9,828 clean 1:1 rows.
The BLS original turned out to be a strict subset of that derivation, 900 pairs
against 913, so the invariant has to be re-established on the pairs we will
actually publish: the thirteen dropped pairs cannot break a 1:1 identity, but
they change WHICH rows are 1:1. Removing a merge edge promotes rows into the
clean set; removing a split edge does too.

THE INVARIANT. For a pair that is 1:1 on both sides -- its SOC2010 maps to one
SOC2018, and that SOC2018 draws on no other SOC2010 -- stage 5's collapse
averages a single contributing row, so the target's exp_change_* must equal the
source's to the last bit. Anything else means the merge or the collapse is
wrong, and the crosswalk cannot be published.

METHOD. Not a re-implementation: this calls the pipeline's own collapse, per
year, with the same right-join and the same float64-accumulate/float32-store
rule as _build_crosswalk_taxonomy, so a discrepancy here is a discrepancy in the
thing that ships.

Run with the pinned venv, never system Python:
    ./.venv/bin/python scripts/verify_soc2018_roundtrip_bls_20260806.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daioe import config as cfgmod  # noqa: E402
from daioe import io  # noqa: E402
from daioe import stata_ops as so  # noqa: E402

CW_BLS = ROOT / "data/derived/soc2010_to_soc2018_BLS.dta"
CW_ONET = ROOT / "data/derived/soc2010_to_soc2018.dta"
PANEL = ROOT / "data/out/daioe_panel_soc.dta"


def load_cw(path: Path) -> pd.DataFrame:
    cw = io.read_dta(str(path))
    cw = cw[["SOC2010code", "SOC2018code"]].copy()
    for c in cw.columns:
        cw[c] = cw[c].astype(str).str.strip()
    return cw.drop_duplicates().reset_index(drop=True)


def clean_pairs(cw: pd.DataFrame) -> pd.DataFrame:
    fan_out = cw.groupby("SOC2010code")["SOC2018code"].nunique()
    fan_in = cw.groupby("SOC2018code")["SOC2010code"].nunique()
    return cw[cw["SOC2010code"].map(fan_out).eq(1) & cw["SOC2018code"].map(fan_in).eq(1)]


def collapse_like_stage5(cfg, soc: pd.DataFrame, cw: pd.DataFrame,
                         change_cols: list[str]) -> pd.DataFrame:
    """The pipeline's own per-year right-join and unweighted-mean collapse."""
    soc_m = soc.rename(columns={"occ_code_soc": "SOC2010code"}).copy()
    soc_m["SOC2010code"] = soc_m["SOC2010code"].astype(str).str.strip()
    for c in change_cols:
        soc_m[c] = soc_m[c].astype("float64")

    pieces = []
    for year in cfg.years:
        sub = soc_m[soc_m["year"] == year]
        m = sub.merge(cw, on="SOC2010code", how="right")
        m["year"] = float(year)
        pieces.append(so.collapse_mean(m, by=["SOC2018code", "year"],
                                       mean_cols=change_cols, first_cols=[]))
    out = pd.concat(pieces, ignore_index=True)
    for c in change_cols:
        out[c] = so.f32(out[c])
    return out


def verify(label: str, cwpath: Path, cfg, soc: pd.DataFrame,
           change_cols: list[str]) -> dict:
    print(f"\n{'='*70}\n{label}: {cwpath.name}\n{'='*70}")
    cw = load_cw(cwpath)
    cl = clean_pairs(cw)
    print(f"  pairs {len(cw)}   clean 1:1 pairs {len(cl)}")

    tgt = collapse_like_stage5(cfg, soc, cw, change_cols)

    # the source side, restricted to the clean pairs, on the same float32 footing
    src = soc.rename(columns={"occ_code_soc": "SOC2010code"}).copy()
    src["SOC2010code"] = src["SOC2010code"].astype(str).str.strip()
    src = src.merge(cl, on="SOC2010code", how="inner")
    for c in change_cols:
        src[c] = so.f32(src[c].astype("float64"))
    src["year"] = src["year"].astype(float)

    j = src.merge(tgt, on=["SOC2018code", "year"], suffixes=("_src", "_tgt"),
                  how="inner", validate="one_to_one")
    print(f"  clean 1:1 rows compared: {len(j)}")

    worst = 0.0
    nanmis = 0
    per_col = {}
    for c in change_cols:
        a = j[f"{c}_src"].to_numpy(dtype="float64")
        b = j[f"{c}_tgt"].to_numpy(dtype="float64")
        both_nan = np.isnan(a) & np.isnan(b)
        one_nan = np.isnan(a) ^ np.isnan(b)
        nanmis += int(one_nan.sum())
        ok = ~(both_nan | one_nan)
        d = float(np.max(np.abs(a[ok] - b[ok]))) if ok.any() else 0.0
        per_col[c] = d
        worst = max(worst, d)

    print(f"  columns compared: {len(change_cols)}")
    print(f"  max|diff| across all columns: {worst:.6e}")
    print(f"  NaN-mask mismatches:          {nanmis}")
    bad = {k: v for k, v in per_col.items() if v > 0}
    if bad:
        print("  columns with any difference:")
        for k, v in sorted(bad.items(), key=lambda kv: -kv[1]):
            print(f"    {k}: {v:.6e}")
    verdict = (worst == 0.0 and nanmis == 0)
    print(f"  VERDICT: {'PASS -- identity exact' if verdict else 'FAIL'}")
    return {"label": label, "pairs": len(cw), "clean": len(cl), "rows": len(j),
            "max": worst, "nan": nanmis, "pass": verdict}


def main() -> None:
    cfg = cfgmod.load_config()
    change_cols = [f"exp_change_{a}" for a in cfg.app_categories]
    print(f"exp_change columns ({len(change_cols)}): {', '.join(change_cols)}")

    if not PANEL.exists():
        print(f"FATAL: frozen SOC panel absent at {PANEL}")
        sys.exit(1)
    soc = io.read_dta(str(PANEL))
    print(f"frozen SOC panel: {soc.shape[0]} rows, "
          f"{soc['occ_code_soc'].nunique()} SOC codes, "
          f"years {int(soc['year'].min())}-{int(soc['year'].max())}")

    results = [verify("BLS ORIGINAL (to be published)", CW_BLS, cfg, soc, change_cols)]
    if CW_ONET.exists():
        results.append(verify("O*NET derivation (4 Aug, for comparison)",
                              CW_ONET, cfg, soc, change_cols))

    print(f"\n{'='*70}\nSUMMARY\n{'='*70}")
    for r in results:
        print(f"  {r['label']:<44} pairs {r['pairs']:>4}  clean {r['clean']:>4}  "
              f"rows {r['rows']:>6}  max|diff| {r['max']:.3e}  "
              f"{'PASS' if r['pass'] else 'FAIL'}")
    if not results[0]["pass"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
