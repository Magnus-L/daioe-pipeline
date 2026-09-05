"""Ship the frozen standardisation moments so users cannot compute them wrongly.

The paper standardises the exposure index on moments frozen over 2010-2020, and
DOCUMENTATION.md instructs users to do the same. This script computes those
moments once, per taxonomy panel and per daioe_* column, over the 2010-2020
rows of the publication panels, and writes them to
data/derived/standardisation_moments_v1.csv for inclusion in the release
bundle. Columns with no 2010-2020 history (daioe_agentic, daioe_mathsci) get
no row, by design: they have no pre-shock units to standardise into.

Scope follows the bundle: v1.0.0 ships the paper's column set, so pass no
argument for the v1.0.0 file; pass --include-g2 at the v1.1.0 bundle build to
add the second-generation composites' rows.
"""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "data/vintage/vintage_2025_v110rc3_20260905/out/Publication"
rows = []
for f in sorted(PUB.glob("daioe_*.dta")):
    d = pd.read_stata(f)
    w = d[(d.year >= 2010) & (d.year <= 2020)]
    include_g2 = "--include-g2" in sys.argv
    for c in [c for c in d.columns if c.startswith("daioe_")]:
        if c.startswith("daioe_g2") and not include_g2:
            continue
        v = w[c].dropna()
        if len(v) == 0:
            continue
        rows.append({"taxonomy": f.stem.removeprefix("daioe_"), "column": c,
                     "window": "2010-2020", "mean": v.mean(), "sd": v.std(),
                     "n_cells": len(v)})
out = pd.DataFrame(rows)
p = ROOT / "data/derived/standardisation_moments_v1.csv"
out.to_csv(p, index=False)
print(f"{p.name}: {len(out)} rows ({out.taxonomy.nunique()} taxonomies, "
      f"{out.column.nunique()} columns)")
