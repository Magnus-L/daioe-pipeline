"""Unit tests for the Stata-idiom shims, with hand-computed expectations.

If these pass we can trust that the four idioms behave like Stata; if a stage panel
later mismatches, the bug is in the stage logic, not the shims.
"""
import numpy as np
import pandas as pd
import pytest

from daioe import stata_ops as so


def test_cumsum_by_treats_missing_as_zero_and_respects_order():
    # deliberately unsorted input
    df = pd.DataFrame(
        {
            "g": ["A", "B", "A", "A", "B"],
            "year": [2012, 2011, 2010, 2011, 2010],
            "v": [3.0, 5.0, 1.0, np.nan, 2.0],
        }
    )
    out = so.cumsum_by(df, group="g", value="v", order="year")
    # A sorted by year: 2010=1 -> 1 ; 2011=NaN -> 1 ; 2012=3 -> 4
    # B sorted by year: 2010=2 -> 2 ; 2011=5 -> 7
    expected = {
        (2012, "A"): 4.0,
        (2011, "B"): 7.0,
        (2010, "A"): 1.0,
        (2011, "A"): 1.0,
        (2010, "B"): 2.0,
    }
    got = {(r.year, r.g): out.loc[i] for i, r in df.iterrows()}
    assert got == expected


def test_group_total_broadcasts_and_skips_missing():
    df = pd.DataFrame({"g": ["A", "A", "A", "B", "B"], "v": [1.0, np.nan, 3.0, 2.0, 5.0]})
    out = so.group_total(df, group="g", value="v")
    assert list(out) == [4.0, 4.0, 4.0, 7.0, 7.0]


def test_group_total_all_missing_group_is_zero():
    df = pd.DataFrame({"g": ["A", "A"], "v": [np.nan, np.nan]})
    out = so.group_total(df, group="g", value="v")
    assert list(out) == [0.0, 0.0]


def test_collapse_mean_skips_missing_and_keeps_first():
    df = pd.DataFrame(
        {
            "g": ["A", "A", "A", "B", "B"],
            "title": ["a", "a", "a", "b", "b"],
            "v": [1.0, np.nan, 3.0, 2.0, 5.0],
        }
    )
    out = so.collapse_mean(df, by="g", mean_cols=["v"], first_cols=["title"])
    assert list(out["g"]) == ["A", "B"]
    assert list(out["title"]) == ["a", "b"]
    assert out.loc[out.g == "A", "v"].iloc[0] == pytest.approx(2.0)   # mean of 1,3
    assert out.loc[out.g == "B", "v"].iloc[0] == pytest.approx(3.5)   # mean of 2,5


def test_pctl_rank_midpoint_formula_and_nan_passthrough():
    df = pd.DataFrame(
        {
            "year": [2010, 2010, 2010, 2010, 2011, 2011],
            "x": [30.0, 10.0, 20.0, np.nan, 5.0, 15.0],
        }
    )
    out = so.pctl_rank(df, value="x", out="pr", by="year")
    # 2010: 3 non-missing sorted 10,20,30 -> ranks 1,2,3 -> (0.5,1.5,2.5)/3*100
    by_val = {df.loc[i, "x"]: out.loc[i] for i in df.index[:3]}
    assert by_val[10.0] == pytest.approx(16.67)
    assert by_val[20.0] == pytest.approx(50.00)
    assert by_val[30.0] == pytest.approx(83.33)
    assert np.isnan(out.loc[3])  # NaN value -> NaN rank
    # 2011: 2 non-missing 5,15 -> (0.5,1.5)/2*100 = 25, 75
    assert out.loc[4] == pytest.approx(25.0)
    assert out.loc[5] == pytest.approx(75.0)


def test_encode_is_alphabetical_one_based():
    s = pd.Series(["banana", "apple", "cherry", "apple"])
    out = so.encode(s)
    assert list(out) == [2, 1, 3, 1]
