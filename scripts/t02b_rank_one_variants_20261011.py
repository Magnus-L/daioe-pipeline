"""Rank-one shares quoted in AI Unboxed, OA Section C4, that t02 does not print (11 Oct 2026).

t02_dynamic_content_20260808.py prints the uncentred rank-one shares of the
occupation-year LEVELS (0.999) and ANNUAL CHANGES (0.991), and the centred share of
the nine application progress paths (0.41). The OA also quotes the two companions:
  - the annual changes centred within occupation (each row demeaned): 96.8 per cent;
  - the application paths uncentred: 65 per cent.
Same inputs and construction as t02, so the four numbers come from one place.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from daioe import io as dio  # noqa: E402  (t02's reader)


def rank1_share(M: np.ndarray) -> float:
    """Share of the squared Frobenius norm captured by the first singular value."""
    s = np.linalg.svd(M, compute_uv=False)
    return float(s[0] ** 2 / (s ** 2).sum())


# occupation x year cumulative index, as in t02.rank_one()
onet = dio.read_dta(ROOT / "data/out/daioe_panel_onet.dta")
X = onet.pivot_table(index="occ_code_onet", columns="year",
                     values="exp_cumul_allapps").dropna().values
D = np.diff(X, axis=1)
print(f"levels, uncentred:                     {rank1_share(X):.3f}")
print(f"annual changes, uncentred:             {rank1_share(D):.3f}")
print(f"annual changes, centred by occupation: {rank1_share(D - D.mean(axis=1, keepdims=True)):.3f}")

# application x year progress paths, as in t02.subdomain_curves()
sl = pd.read_parquet(ROOT / "data/out/slopes_slimmed_allapps.parquet")
sl = sl[(sl["year"] >= 2010) & (sl["parent_name"] != "robotics")]
P = sl.pivot_table(index="year", columns="parent_name", values="mean").fillna(0.0).values.T
print(f"application paths, centred:            {rank1_share(P - P.mean(axis=1, keepdims=True)):.3f}")
print(f"application paths, uncentred:          {rank1_share(P):.3f}")
