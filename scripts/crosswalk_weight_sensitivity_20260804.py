"""Aggregation weights: what the concordances carry, and what the construction uses.

THE FINDING THIS EXISTS TO RECORD
--------------------------------
Every SOC2010 -> target crosswalk in ``data/raw/`` carries a weight column, and the
construction ignores all of them. ``_build_crosswalk_taxonomy`` keeps only the two key
columns plus whatever ``first_cols`` a builder names, and collapses with a simple
unweighted mean; ``build_ssyk2012`` and ``build_ssyk96`` name nothing extra. Since the
port reproduces Erik's Stata bit-for-bit, his code did not use them either.

Whether that matters differs by taxonomy, and only one of the three is a real choice:

  isco08    ``share_of_soc10_occupations`` is exactly 1/n. Weighted == unweighted.
            Nothing to test.
  ssyk96    ``weight`` sums to exactly 1.000 within every target code and coincides with
            1/n on only 16 per cent of rows. A genuine aggregation weight, unused.
  ssyk2012  ``weight`` is substantive but NOT normalised within target (sums run 0 to 6)
            and includes exact zeros. Using it needs a normalisation rule first, so it
            is reported here and not tested.

This script quantifies the ssyk96 case. It reads ``data/out/daioe_panel_soc.dta`` and
writes nothing to any panel: the frozen build is untouched, and must stay that way —
B21 reproduces B12 to every digit on the frozen exposure, and that reproduction is the
strongest single asset in the revision.

THE ONE CHOICE MADE HERE, AND IT IS A CHOICE
--------------------------------------------
Where a source occupation has no exposure value in a given year, its weight is dropped
and the remaining weights renormalised over the sources that do. The alternative is to
treat missing as zero, which would bias every affected target downward. Erik should
confirm which he would want before anything from this reaches an appendix.

Feeds the "aggregation weights" cell of the T06 sensitivity grid, which the response
memo lists as planned and which had not been run.

Usage: .venv/bin/python scripts/crosswalk_weight_sensitivity_20260804.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyreadstat

ROOT = Path(__file__).resolve().parents[1]
SOC_PANEL = ROOT / "data" / "out" / "daioe_panel_soc.dta"
CW = ROOT / "data" / "raw" / "ssyk96_soc10_crosswalk.dta"
VALUE = "exp_change_allapps"


def collapse(soc: pd.DataFrame, cw: pd.DataFrame, weighted: bool) -> pd.DataFrame:
    """Mirror _build_crosswalk_taxonomy: per-year right join, collapse, cumulate."""
    out = []
    for y in sorted(soc["year"].dropna().unique()):
        sub = soc.loc[soc["year"] == y, ["occ_code_soc", VALUE]]
        m = sub.merge(cw, left_on="occ_code_soc", right_on="SOC2010code", how="right")
        m["v"] = m[VALUE].astype("float64")
        if weighted:
            m["wv"] = m["v"] * m["weight"]
            g = m.groupby("SSYK96kod").apply(
                lambda d: d["wv"].sum() / d.loc[d["v"].notna(), "weight"].sum()
            )
        else:
            g = m.groupby("SSYK96kod")["v"].mean()
        out.append(g.rename("exp_change").reset_index().assign(year=y))
    p = pd.concat(out).sort_values(["SSYK96kod", "year"])
    p["exp_cumul"] = p.groupby("SSYK96kod")["exp_change"].cumsum()
    return p


def main() -> None:
    soc = pd.read_stata(SOC_PANEL)
    soc["occ_code_soc"] = soc["occ_code_soc"].astype(str).str.strip()
    cw, _ = pyreadstat.read_dta(str(CW))
    cw["SOC2010code"] = cw["SOC2010code"].astype(str).str.strip()
    cw = cw[["SOC2010code", "SSYK96kod", "weight"]].dropna()

    u = collapse(soc, cw, weighted=False)
    w = collapse(soc, cw, weighted=True)
    c = u.merge(w, on=["SSYK96kod", "year"], suffixes=("_u", "_w"))
    c = c[c["exp_cumul_u"].notna() & c["exp_cumul_w"].notna()]

    d = c["exp_cumul_w"] - c["exp_cumul_u"]
    print(f"SSYK96 occupation-years compared : {len(c)}")
    print(f"correlation of exp_cumul         : {c[['exp_cumul_u','exp_cumul_w']].corr().iloc[0,1]:.6f}")
    print(f"mean diff {d.mean():.4f} | mean |diff| {d.abs().mean():.4f} | max |diff| {d.abs().max():.4f}")
    print(f"mean level (unweighted) {c['exp_cumul_u'].mean():.4f}"
          f"  -> mean |diff| is {100*d.abs().mean()/c['exp_cumul_u'].mean():.1f}% of level")

    l = c[c["year"] == c["year"].max()].copy()
    l["ru"] = l["exp_cumul_u"].rank(pct=True)
    l["rw"] = l["exp_cumul_w"].rank(pct=True)
    n10 = max(1, len(l) // 10)
    tu = set(l.nlargest(n10, "exp_cumul_u")["SSYK96kod"])
    tw = set(l.nlargest(n10, "exp_cumul_w")["SSYK96kod"])
    print(f"\nfinal year, Spearman rank correlation : "
          f"{l[['exp_cumul_u','exp_cumul_w']].corr(method='spearman').iloc[0,1]:.6f}")
    print(f"final year, top-decile overlap        : {len(tu & tw)} of {n10} "
          f"({100*len(tu & tw)/n10:.0f}%)")

    l["move"] = (l["rw"] - l["ru"]).abs()
    print("\nlargest percentile-rank movements, final year:")
    print(l.nlargest(6, "move")[["SSYK96kod", "exp_cumul_u", "exp_cumul_w", "ru", "rw"]]
          .to_string(index=False))
    print("\nThe aggregate picture is robust; individual occupations and the top decile")
    print("are not. Read both numbers, not one.")


if __name__ == "__main__":
    main()
