"""Panel-structure gate (added 4 Sep 2026, after the 68-row investigation).

Fatal check on every publication panel of a staged vintage:
  1. no missing occupation key anywhere;
  2. unique (occupation, year) pairs among year-carrying rows;
  3. year-less rows are permitted ONLY where the deposited v1.0.0 frozen file
     carries the same year-less row for the same code (an inherited property of
     the original construction's crosswalk: 68 such rows in SOC 2010, none
     elsewhere), and their count must match exactly;
  4. year-carrying rows must be exactly (occupations x years) for the panel.

Usage: python scripts/gate_panel_structure.py <staged-vintage-dir>
Exits non-zero on any violation. Run before every deposit.
"""
import sys
from pathlib import Path
import pandas as pd

V0 = Path("dist/daioe-v1.0.0-scores/frozen-2010-2023")
PANELS = ["daioe_onetsoc2010", "daioe_soc2010", "daioe_isco08",
          "daioe_ssyk2012", "daioe_ssyk96"]

def keycol(df):
    return [c for c in df.columns
            if c.startswith("occ_code") or c in ("isco08_4","ssyk2012_4","ssyk96_4")][0]

def main(staged: Path) -> int:
    failures = []
    for name in PANELS:
        f = next(staged.rglob(name + ".dta"), None)
        if f is None:
            failures.append(f"{name}: panel missing"); continue
        d = pd.read_stata(f); k = keycol(d)
        if d[k].isna().any():
            failures.append(f"{name}: missing occupation keys")
        yl = d[d.year.isna()]
        v0f = V0 / f"{name}.dta"
        allowed = set()
        if v0f.exists():
            v0 = pd.read_stata(v0f)
            allowed = set(v0[v0.year.isna()][keycol(v0)])
        got = set(yl[k])
        if got != allowed or len(yl) != len(allowed):
            failures.append(f"{name}: year-less rows {len(yl)} (codes {len(got)}) "
                            f"vs allowed {len(allowed)} inherited from v1.0.0")
        g = d.dropna(subset=["year"])
        if g.duplicated([k, "year"]).any():
            failures.append(f"{name}: duplicate occupation-year pairs")
        expect = g[k].nunique() * g.year.nunique()
        if len(g) != expect:
            failures.append(f"{name}: {len(g)} year-carrying rows, expected "
                            f"{g[k].nunique()} x {g.year.nunique()} = {expect}")
        print(f"  {name}: {len(g)} + {len(yl)} year-less "
              f"({'OK' if not [x for x in failures if x.startswith(name)] else 'FAIL'})")
    if failures:
        print("\nGATE FAILED:"); [print("  -", x) for x in failures]; return 1
    print("\nPanel-structure gate: PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1
                  else Path("data/vintage/vintage_2025_v110rc_20260824")))
