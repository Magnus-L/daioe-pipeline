"""The errata-application mechanism (VINTAGES.md policy, implemented 25 Aug 2026).

Synthetic-frame tests of the two guards and the two correction kinds; the real-data
smoke check (all four declared errata match exactly one frozen-sheet row) runs in
test_errata_match_real_sheet, so a drifted source sheet fails loudly here rather
than at a future vintage build.
"""
from pathlib import Path

import pandas as pd
import pytest

from daioe import config as cfgmod
from daioe.stage2_ai_progress import _apply_errata

ROOT = Path(__file__).resolve().parents[1]


def _cfg(tmp_path, year_final=2026, errata_rows=None):
    d = tmp_path / "data" / "derived"
    d.mkdir(parents=True, exist_ok=True)
    rows = errata_rows if errata_rows is not None else [
        {"erratum_id": "T1", "metrics_name": "m1", "name": "modelA", "field": "value",
         "frozen_value": 26.9, "correct_value": 26.4, "applies": "next_chain_point",
         "evidence": "test"},
        {"erratum_id": "T2", "metrics_name": "m2", "name": "OLDNAME", "field": "name",
         "frozen_value": "OLDNAME", "correct_value": "NEWNAME",
         "applies": "next_chain_point", "evidence": "test"},
    ]
    pd.DataFrame(rows).to_csv(d / "errata_frozen_workbook_v1.csv", index=False)
    return cfgmod.Config(raw={"base_year": 2010, "year_final": year_final},
                         root=tmp_path)


def _sheet():
    return pd.DataFrame({
        "metrics_name": ["m1", "m1", "m2"],
        "name": ["modelA", "modelB", "OLDNAME"],
        "value": [26.9, 30.0, 50.0],
        "date": ["2016-01-01"] * 3,
        "parent_name": ["p"] * 3,
        "papername": ["q"] * 3,
    })


def test_value_and_name_errata_apply(tmp_path):
    out = _apply_errata(_sheet(), _cfg(tmp_path))
    assert len(out) == 3
    assert out.loc[out["name"] == "modelA", "value"].item() == pytest.approx(26.4)
    assert (out["name"] == "NEWNAME").sum() == 1 and (out["name"] == "OLDNAME").sum() == 0
    # untouched row untouched
    assert out.loc[out["name"] == "modelB", "value"].item() == pytest.approx(30.0)


def test_frozen_build_refuses(tmp_path):
    with pytest.raises(ValueError, match="frozen-window build"):
        _apply_errata(_sheet(), _cfg(tmp_path, year_final=2023))


def test_unmatched_erratum_is_fatal(tmp_path):
    cfg = _cfg(tmp_path, errata_rows=[
        {"erratum_id": "TX", "metrics_name": "absent", "name": "nobody",
         "field": "value", "frozen_value": 1.0, "correct_value": 2.0,
         "applies": "next_chain_point", "evidence": "test"}])
    with pytest.raises(AssertionError, match="matched 0 rows"):
        _apply_errata(_sheet(), cfg)


def test_errata_match_real_sheet():
    """All four declared errata must match exactly one row of the real frozen sheet."""
    from daioe import io
    real = cfgmod.load_config(ROOT / "config.yaml")
    ms = io.read_excel_sheet(real.raw_file("measures_metrics_newdata2023.xlsx"),
                             sheet="measures")
    new = ms[["parent_name", "metrics_name", "papername", "name", "date", "value"]]
    new = new[new["metrics_name"].notna()
              & (new["metrics_name"].astype(str).str.strip() != "")]
    seam = cfgmod.Config(raw={**real.raw, "year_final": 2026}, root=real.root)
    out = _apply_errata(new, seam)   # the one-row asserts inside are the test
    assert len(out) == len(new)
