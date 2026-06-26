"""Stata-idiom shims.

These reproduce the exact semantics of the Stata operations the DAIOE pipeline
relies on. The dangerous part of a Stata->pandas port is that superficially similar
operations differ in missing-value handling and ordering; getting these four wrong
silently corrupts every downstream panel. Each shim documents the Stata behaviour it
mirrors and is unit-tested in tests/test_stata_ops.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def cumsum_by(
    df: pd.DataFrame,
    group: str | list[str],
    value: str,
    order: str | list[str],
    out: str | None = None,
) -> pd.Series:
    """Mirror Stata ``by group (order): gen out = sum(value)``.

    Stata's running ``sum()`` function:
      * processes rows in (group, order) sort order,
      * treats missing values of ``value`` as 0 (they contribute nothing),
      * NEVER returns missing — every row gets the running total so far.

    pandas' ``groupby.cumsum`` instead PROPAGATES NaN, so we fill with 0 first.
    The result is returned aligned to ``df``'s original index.
    """
    group = [group] if isinstance(group, str) else list(group)
    order = [order] if isinstance(order, str) else list(order)
    # Stable sort on (group, order); mergesort keeps the input order for ties,
    # matching Stata's stable sort when the sort keys do not fully determine order.
    ordered = df.sort_values(group + order, kind="mergesort")
    filled = ordered[value].fillna(0.0)
    result = filled.groupby([ordered[g] for g in group], sort=False).cumsum()
    result = result.reindex(df.index)
    if out is not None:
        result = result.rename(out)
    return result


def group_total(
    df: pd.DataFrame,
    group: str | list[str],
    value: str,
    out: str | None = None,
) -> pd.Series:
    """Mirror Stata ``egen out = sum(value), by(group)`` (group total, broadcast).

    Stata's ``egen ... = sum()`` is the within-group TOTAL (not cumulative),
    broadcast to every row in the group, treating missing as 0. If all values in a
    group are missing, the total is 0. pandas ``transform('sum')`` skips NaN (i.e.
    treats them as 0) and returns 0 for an all-NaN group, matching exactly.
    """
    group = [group] if isinstance(group, str) else list(group)
    result = df.groupby(group, sort=False, dropna=False)[value].transform("sum")
    if out is not None:
        result = result.rename(out)
    return result


def collapse_mean(
    df: pd.DataFrame,
    by: str | list[str],
    mean_cols: list[str],
    first_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Mirror Stata ``collapse (mean) mean_cols (first) first_cols, by(by)``.

    Stata ``collapse (mean)`` computes the mean of NON-missing values (NaN-skipping),
    returning missing only if every value in the group is missing. pandas
    ``groupby.mean`` skips NaN by default and returns NaN for an all-NaN group, which
    matches. ``(first)`` columns are constant within a group in this pipeline (titles),
    so first non-missing is taken. Rows are returned sorted by the by-keys, as Stata
    leaves a collapsed dataset sorted by its by-list.
    """
    by = [by] if isinstance(by, str) else list(by)
    first_cols = first_cols or []
    agg = {c: "mean" for c in mean_cols}
    agg.update({c: "first" for c in first_cols})
    out = (
        df.groupby(by, sort=True, dropna=False)
        .agg(agg)
        .reset_index()
    )
    # preserve column order: by, then first_cols, then mean_cols (collapse output order)
    return out[by + first_cols + mean_cols]


def pctl_rank(
    df: pd.DataFrame,
    value: str,
    out: str,
    by: str = "year",
) -> pd.Series:
    """Mirror the Stata ``pctl_rank`` program.

    Within each ``by`` group, among NON-missing ``value`` rows sorted ascending::

        rank          = 1..n   (cumulative count of non-missing)
        rows_per_year = n      (count of non-missing in the group)
        out           = round((rank - 0.5) / rows_per_year * 100, 0.01)

    Rows with missing ``value`` get missing ``out``. Ties are broken by the input
    order (Stata's ``sort year value`` is stable on the remaining order); on tied
    values this is a documented near-exact risk surfaced by the validation report.
    """
    result = pd.Series(np.nan, index=df.index, name=out)
    notna = df[value].notna()
    for _, idx in df.index.to_series().groupby(df[by], sort=False):
        sub = df.loc[idx]
        mask = sub[value].notna()
        valid = sub.loc[mask]
        if len(valid) == 0:
            continue
        # stable ascending sort by value; ranks 1..n
        order = valid[value].sort_values(kind="mergesort").index
        n = len(order)
        ranks = np.arange(1, n + 1, dtype=float)
        pct = np.round((ranks - 0.5) / n * 100.0, 2)
        result.loc[order] = pct
    return result


def encode(series: pd.Series) -> pd.Series:
    """Mirror Stata ``encode`` (alphabetical levels, 1-based integer codes)."""
    codes, _ = pd.factorize(series, sort=True)
    return pd.Series(codes + 1, index=series.index)


def stata_round(x, digits: int = 2):
    """Round to a number of decimals as Stata ``round(x, 10^-digits)`` does."""
    return np.round(x, digits)
