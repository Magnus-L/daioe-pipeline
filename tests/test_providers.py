"""Tests for the provider layer: the registry's admission rule and the Epoch adapter.

The point of these is that the guards fire. A provider that silently accepts a series missing
its scale, its anchor or its licence would reintroduce exactly the failure modes the admission
rule exists to prevent, and those failures are invisible downstream: an unknown scale yields
NaN value_scaled with no error path.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from daioe.providers import SeriesSpec, load_registry
from daioe.providers import epoch


def _spec(**over):
    base = dict(
        metrics_name="M", parent_name="P", source="epoch", source_series="s",
        score_col="EM", date_col="Release date", scale="Percentage correct",
        anchor=90.0, anchor_kind="human", protocol="pure_model",
        licence="CC BY 4.0", source_note="checked",
    )
    base.update(over)
    return SeriesSpec(**base)


# --------------------------- the admission rule ---------------------------

def test_unknown_scale_is_refused():
    with pytest.raises(ValueError, match="not one of the eight"):
        _spec(scale="Vibes").validate()


def test_unclean_licence_is_refused():
    """CC BY-ND cannot enter a redistributed derived index at all."""
    with pytest.raises(ValueError, match="not cleared for"):
        _spec(licence="CC BY-ND 4.0").validate()


def test_bad_protocol_is_refused():
    with pytest.raises(ValueError, match="protocol must be"):
        _spec(protocol="mixed").validate()


def test_missing_source_note_is_refused():
    """A registry entry is a claim someone checked; it must say what was checked."""
    with pytest.raises(ValueError, match="source_note is required"):
        _spec(source_note="").validate()


def test_duplicate_metric_is_refused(tmp_path: Path):
    rows = [_spec().__dict__, _spec().__dict__]
    p = tmp_path / "r.json"
    p.write_text(json.dumps(rows))
    with pytest.raises(ValueError, match="declared twice"):
        load_registry(p)


def test_shipped_registry_validates():
    """The registry we actually ship must pass its own rule."""
    root = Path(__file__).resolve().parents[1]
    specs = load_registry(root / "data/derived/series_registry_v1.json")
    assert specs, "registry is empty"
    for s in specs:
        s.validate()


# --------------------------- the Epoch adapter ---------------------------

def _frame(values, dates):
    return pd.DataFrame({
        "EM": values, "Release date": dates,
        "Model version": [f"m{i}" for i in range(len(values))],
    })


def test_frontier_is_running_max_for_higher_is_better():
    df = _frame([0.5, 0.4, 0.7, 0.6], ["2020-01-01", "2021-01-01", "2022-01-01", "2023-01-01"])
    front, q = epoch._frontier(df, _spec(value_multiplier=100.0))
    assert list(front["value"]) == [50.0, 70.0]
    assert q["undated_rows"] == 0


def test_frontier_is_running_min_for_lower_is_better():
    df = _frame([9.0, 7.0, 8.0], ["2020-01-01", "2021-01-01", "2022-01-01"])
    front, _ = epoch._frontier(df, _spec(scale="Percentage error"))
    assert list(front["value"]) == [9.0, 7.0]


def test_undated_rows_are_quarantined_not_dropped_silently():
    """An undated row BELOW the dated frontier is recorded and excluded, not fatal."""
    df = _frame([0.5, 0.45, 0.6], ["2020-01-01", None, "2022-01-01"])
    front, q = epoch._frontier(df, _spec(value_multiplier=100.0))
    assert q["undated_rows"] == 1
    assert "m1" in q["undated_models"]
    assert list(front["value"]) == [50.0, 60.0]   # the undated row never enters


def test_undated_row_above_the_frontier_is_fatal():
    """If the best model is undated the frontier we build is simply wrong."""
    df = _frame([0.5, 0.99, 0.6], ["2020-01-01", None, "2022-01-01"])
    with pytest.raises(ValueError, match="exceed the dated frontier"):
        epoch._frontier(df, _spec(value_multiplier=100.0))


def test_all_undated_is_fatal():
    df = _frame([0.5, 0.6], [None, None])
    with pytest.raises(ValueError, match="every row is undated"):
        epoch._frontier(df, _spec())


def test_missing_series_file_names_the_metric(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="is in the Epoch"):
        epoch.build_updates([_spec(source_series="nope")], tmp_path)


def test_epoch_run_and_external_files_are_distinguished(tmp_path: Path):
    """Epoch names its own harness runs '<s>.csv' and collected scores '<s>_external.csv'.

    The distinction is not cosmetic: an Epoch-run series has one known evaluation protocol
    while an external one carries whatever the reporter used, so which file was read has to
    reach provenance.
    """
    df = _frame([0.5, 0.7], ["2024-01-01", "2025-01-01"])
    (tmp_path / "s.csv").write_text(df.to_csv(index=False))
    _, prov = epoch.build_updates([_spec(value_multiplier=100.0)], tmp_path)
    assert prov["files"]["s.csv"]["evaluation"] == "epoch-run"

    (tmp_path / "s.csv").unlink()
    (tmp_path / "s_external.csv").write_text(df.to_csv(index=False))
    _, prov = epoch.build_updates([_spec(value_multiplier=100.0)], tmp_path)
    assert prov["files"]["s_external.csv"]["evaluation"] == "external"
