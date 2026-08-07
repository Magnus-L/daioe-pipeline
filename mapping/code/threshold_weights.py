"""
threshold_weights.py — required levels and occupation weights for the level-threshold track.

Parallel track. Nothing here writes to `src/daioe/` or `data/out/`, and nothing existing consumes it.

Two objects per element block:

    required[o, j]   what level occupation o needs of element j, on O*NET's RAW scale (0-7)
    weight[o, j]     how much of o's work element j accounts for

**Required levels must come from the raw O*NET workbooks.** `data/out/onet_abilities_weighted.parquet`
keeps only `level_scaled` (0 to 0.911), which is the level divided by its scale maximum and then
folded into `element_impact`. The threshold compares an attained level against a required level on
the anchored 1-7 scale, so a normalised share is the wrong object; reading the workbooks directly is
not duplication but the only way to get the number the anchors refer to.

**Weights follow the existing convention exactly**: each block is a share of its own full O*NET
domain, never of the sub-block. The 52 abilities share the abilities domain, the 6 social skills share
the 35-skill domain (so they sum to a varying ~0.21), the 17 social activities share the 41-activity
domain (a varying 0.18 to 0.59). Normalising within a sub-block instead makes every occupation's
block sum to 1 and erases the cross-occupation variation in intensity, which is the bug that put
glass blowers at the top of the social ranking earlier today.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

MAP = Path(__file__).resolve().parents[1]
ROOT = MAP.parent
RAWD = ROOT / "data" / "raw"

# block -> (workbook, regex selecting that domain's leaf elements). The two activity blocks share
# a workbook and a domain deliberately: their weights are shares of the SAME 41-activity domain, so
# together they sum to 1 per occupation and the task-level construction is a complete decomposition.
SOURCES = {
    "ability":            ("Abilities_Onet_Feb2018_22_2.xlsx",       r"^1\.A\."),
    "social_skill":       ("Skills_Onet_Feb2018_22_2.xlsx",          r"^2\.[AB]\."),
    "activity":           ("Work_Activities_Onet_Feb2018_22_2.xlsx", r"^4\.A\."),
    "activity_nonsocial": ("Work_Activities_Onet_Feb2018_22_2.xlsx", r"^4\.A\."),
}


def _read(workbook: str, domain: str) -> pd.DataFrame:
    d = pd.read_excel(RAWD / workbook)
    d.columns = [c.strip() for c in d.columns]
    d = d[d["Element ID"].astype(str).str.match(domain)]
    wide = d.pivot_table(index=["O*NET-SOC Code", "Element ID"], columns="Scale ID",
                         values="Data Value")
    return wide[["LV", "IM"]].dropna()


def block_matrices(block: str, elements: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (required_level, weight) for one block, occupations x elements.

    `weight` is the share of the block's *full* O*NET domain, restricted afterwards to the elements
    we actually score, so an occupation heavy in social activities keeps a larger block sum.
    """
    workbook, domain = SOURCES[block]
    wide = _read(workbook, domain)

    v = (wide["LV"] / 7.0) * (wide["IM"] / 5.0)          # level x importance, each on its own scale
    w_all = v.unstack()
    w_all = w_all.div(w_all.sum(axis=1), axis=0)          # share of the FULL domain

    keep = elements[elements.block == block]["element_id"].tolist()
    missing = [e for e in keep if e not in w_all.columns]
    if missing:
        raise ValueError(f"{block}: elements absent from {workbook}: {missing}")

    required = wide["LV"].unstack()[keep]
    weight = w_all[keep]
    required.index.name = weight.index.name = "occ_code_onet"
    return required, weight


def load(blocks: list[str], elements: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Required levels and weights across several blocks, aligned on occupations.

    Weights are NOT renormalised across blocks: each keeps its own domain share, so the abilities
    backbone contributes 1.0 per occupation and each social block adds its own varying amount. That
    matches how `build_2024_variants.combine` treats the same blocks.
    """
    reqs, wts = [], []
    for b in blocks:
        r, w = block_matrices(b, elements)
        reqs.append(r)
        wts.append(w)
    occ = sorted(set.intersection(*(set(x.index) for x in wts)))
    return (pd.concat([r.loc[occ] for r in reqs], axis=1),
            pd.concat([w.loc[occ] for w in wts], axis=1))


if __name__ == "__main__":
    els = pd.read_csv(MAP / "raw_data" / "abilities_v2.csv")
    for b in SOURCES:
        r, w = block_matrices(b, els)
        print(f"{b:<14} {r.shape[1]:>2} elements, {len(r)} occupations | "
              f"required level {r.values.min():.2f}-{r.values.max():.2f} | "
              f"block weight {w.sum(axis=1).min():.3f}-{w.sum(axis=1).max():.3f}")
