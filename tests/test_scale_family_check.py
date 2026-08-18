"""The scale families are not commensurable; the check is what makes that visible.

These are the properties the module asserts about metric types, as tests, so a future edit
cannot quietly turn the family comparison into a basket comparison again.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from daioe import scale_family_check as sfc


def _fixture(rows):
    """rows: (metrics_name, scale, deltafinal). Builds the two frames the module reads."""
    fr = pd.DataFrame(
        [{"metrics_name": m, "year": 2000 + i, "deltafinal": d} for i, (m, _, d) in enumerate(rows)]
    )
    fd = pd.DataFrame([{"metrics_name": m, "scale": s, "value": 1.0} for m, s, _ in rows])
    return fr, fd


def test_series_is_judged_against_its_own_family_not_the_basket():
    """The whole point: a Score series must not be flagged for beating percentage series."""
    rows = [("pct_a", "Percentage correct", 0.10), ("pct_b", "Percentage correct", 0.12),
            ("pct_c", "Percentage correct", 0.11)]
    rows += [(f"score_{i}", "Score", 0.3 + 0.1 * i) for i in range(10)]   # 0.3 .. 1.2
    rows += [("newcomer", "Score", 1.10)]
    fr, fd = _fixture(rows)
    v = sfc.check_series(fr, fd, "newcomer")
    assert v.scale == "Score"
    assert v.n_family == 10           # compared only with other Score series
    assert not v.flagged              # 1.10 is ordinary for Score, huge next to the pct rows


def test_a_series_that_does_not_behave_like_its_family_is_flagged():
    rows = [(f"score_{i}", "Score", 0.2 + 0.05 * i) for i in range(20)]
    rows += [("runaway", "Score", 40.0)]
    fr, fd = _fixture(rows)
    assert sfc.check_series(fr, fd, "runaway").flagged


def test_a_series_cannot_normalise_its_own_reference():
    """Excluding the series itself matters: many large increments would otherwise self-justify."""
    rows = [(f"score_{i}", "Score", 0.3) for i in range(5)]
    rows += [(f"big_{i}", "Score", 30.0) for i in range(40)]   # same NAME family, many rows
    fr, fd = _fixture(rows)
    # 'big_0' is compared against the other 44, which include 39 other big ones, so it is fine;
    # the guarantee under test is only that its own rows are excluded from the reference.
    v = sfc.check_series(fr, fd, "big_0")
    assert v.n_family == 44
    assert v.n_own == 1


def test_unprecedented_family_reports_rather_than_asserts():
    """A first-of-its-kind family has no reference; that is a fact, not a failure."""
    fr, fd = _fixture([("only", "ELO rating", 2.0)])
    v = sfc.check_series(fr, fd, "only")
    assert v.n_family == 0
    assert not v.flagged
    assert np.isnan(v.percentile)


def test_zero_increments_are_not_counted_as_observations():
    """A saturated metric contributes 0 every year; counting those would drag every family down."""
    rows = [("a", "Score", 0.0), ("b", "Score", 0.0), ("c", "Score", 0.5), ("d", "Score", 0.7)]
    fr, fd = _fixture(rows)
    assert int(sfc.report(fr, fd).loc["Score", "count"]) == 2


def test_missing_series_raises():
    fr, fd = _fixture([("a", "Score", 0.5)])
    with pytest.raises(ValueError, match="no non-zero increments"):
        sfc.check_series(fr, fd, "nonexistent")
