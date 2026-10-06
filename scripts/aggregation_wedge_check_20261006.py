"""Aggregation wedge behind OA Section M (numbers formerly only in a comment of
f2_permutation_generator_20260809.py, lines 72-74).

Wedge = |(sum_d sqrt(exp_change_d))^2 - exp_change| / exp_change over the nine named
applications. Exact at the O*NET level; a Jensen gap appears only where the SSYK 2012
cell averages several SOC 2010 occupations. Cell statistic = median over years;
source count = distinct SOC 2010 codes the ssyk2012_soc10 crosswalk maps into the cell.
Public pipeline outputs only. Run from the daioe-pipeline repo root.
"""
import numpy as np
import pandas as pd

SUBS = ["stratgames", "videogames", "imgrec", "imgcompr", "imggen",
        "readcompr", "lngmod", "translat", "speechrec"]


def rel_wedge(df, total):
    recon = sum(np.sqrt(df[f"exp_change_{s}"].fillna(0).clip(lower=0)) for s in SUBS) ** 2
    return (recon - df[total]).abs() / df[total].where(df[total] > 0)


# O*NET level: identity exact up to float noise
on = pd.read_stata("data/out/daioe_panel_onet.dta")
r_on = rel_wedge(on, "exp_change_allapps")
print(f"O*NET: {r_on.notna().sum()} occupation-years, max rel {r_on.max():.1e}")

# SSYK 2012 level, sample as in the permutation generator
p = pd.read_stata("data/out/daioe_panel_ssyk2012.dta")
p = p[~p["ssyk2012_4"].isin(p.loc[p["exp_change"].isna(), "ssyk2012_4"].unique())].copy()
p["rel"] = rel_wedge(p, "exp_change")
p["ssyk"] = p["ssyk2012_4"].astype(int)

cw = pd.read_stata("data/raw/ssyk2012_soc10_crosswalk.dta")
nsrc = (cw.assign(ssyk=cw["SSYK2012kod"].astype(int))
          .groupby("ssyk")["SOC2010code"].nunique().rename("n_src"))
cell = p.groupby("ssyk")["rel"].median().to_frame().join(nsrc, how="left")
assert cell["n_src"].notna().all()

one, many = cell[cell.n_src == 1], cell[cell.n_src >= 2]
rho = np.corrcoef(cell.rel.rank(), cell.n_src.rank())[0, 1]   # Spearman = Pearson on ranks
print(f"cells {len(cell)}: median {cell.rel.median():.1e}, max {cell.rel.max():.2%}")
print(f"single-source cells {len(one)}: median {one.rel.median():.1e}")
print(f"multi-source cells {len(many)}: median {many.rel.median():.1e}")
print(f"Spearman(wedge, n sources) {rho:.2f}")
