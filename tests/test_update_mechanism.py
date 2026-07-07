"""Tests for the Phase 2 Track A update-workbook mechanism (stage2 _load_updates).

Self-contained: builds a minimal synthetic raw tree (frozen workbook + EFF csvs)
in tmp_path, so the tests run without the gitignored data/ symlinks.
"""

from pathlib import Path

import pandas as pd
import pytest

from daioe.config import Config
from daioe import stage2_ai_progress as s2

FROZEN_METRIC = "Speech Recognition on LibriSpeech test-clean"
FROZEN_APP = "Speech Recognition"


def make_cfg(tmp_path: Path, updates: list[str]) -> Config:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(exist_ok=True)

    frozen = raw_dir / "measures_metrics_newdata2023.xlsx"
    with pd.ExcelWriter(frozen) as xw:
        pd.DataFrame(
            {
                "parent_name_cleaned": ["speech recognition"],
                "parent_name": [FROZEN_APP],
                "metrics_name": [FROZEN_METRIC],
                "name": ["ModelA"],
                "date": ["2022-01-31"],
                "value": [2.5],
                "papername": ["Paper A"],
                "url": [""],
            }
        ).to_excel(xw, sheet_name="measures", index=False)
        pd.DataFrame(
            {
                "parent_name_cleaned": ["speech recognition"],
                "parent_name": [FROZEN_APP],
                "metrics_name": [FROZEN_METRIC],
                "scale": ["Percentage error"],
                "axis_label": ["WER"],
                "url": [""],
                "target": [None],
                "target_label": [None],
                "target_source": [None],
                "data_path": [None],
                "data_url": [None],
                "graphed": [None],
                "notes": [None],
                "solved": [None],
            }
        ).to_excel(xw, sheet_name="metrics", index=False)

    pd.DataFrame(
        columns=["metrics_name", "date", "name", "value", "parent_name", "papername"]
    ).to_csv(raw_dir / "measures.csv", index=False)
    pd.DataFrame(
        columns=["name", "parent_name", "axis_label", "scale", "target", "target_label"]
    ).to_csv(raw_dir / "metrics.csv", index=False)

    raw = {
        "base_year": 2010,
        "year_final": 2024,
        "paths": {"raw": "raw", "enriched_ref": "raw", "reference": "raw",
                  "out": "out", "reports": "reports"},
        "benchmark_updates": updates,
        "tol_internal": 1e-6,
        "tol_publication": 1e-5,
    }
    return Config(raw=raw, root=tmp_path)


def write_update(tmp_path: Path, rows: pd.DataFrame, extra_sheet: bool = False) -> str:
    p = tmp_path / "update.xlsx"
    with pd.ExcelWriter(p) as xw:
        rows.to_excel(xw, sheet_name="measures", index=False)
        if extra_sheet:
            rows.head(0).to_excel(xw, sheet_name="metrics", index=False)
    return "update.xlsx"


def valid_rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "parent_name": [FROZEN_APP],
            "metrics_name": [FROZEN_METRIC],
            "papername": ["Paper B"],
            "name": ["ModelB"],
            "date": ["2024-06-30"],
            "value": [1.8],
        }
    )


def test_empty_updates_is_inert(tmp_path):
    cfg = make_cfg(tmp_path, updates=[])
    assert s2._load_updates(cfg) is None
    base = s2._build_measures(cfg)
    assert len(base) == 1  # only the frozen row


def test_valid_update_appends_as_newdata(tmp_path):
    upd = write_update(tmp_path, valid_rows())
    cfg = make_cfg(tmp_path, updates=[upd])
    out = s2._build_measures(cfg)
    assert len(out) == 2
    new_row = out[out["name"] == "ModelB"].iloc[0]
    assert new_row["newdata2023"] == 1.0
    assert new_row["date"] == "2024-06-30"


def test_extra_sheet_rejected(tmp_path):
    upd = write_update(tmp_path, valid_rows(), extra_sheet=True)
    cfg = make_cfg(tmp_path, updates=[upd])
    with pytest.raises(ValueError, match="only a 'measures' sheet"):
        s2._load_updates(cfg)


def test_unknown_metric_rejected(tmp_path):
    rows = valid_rows().assign(metrics_name="Totally New Benchmark on X")
    upd = write_update(tmp_path, rows)
    cfg = make_cfg(tmp_path, updates=[upd])
    with pytest.raises(ValueError, match="basket-faithful"):
        s2._load_updates(cfg)


def test_wrong_parent_rejected(tmp_path):
    rows = valid_rows().assign(parent_name="Image classification")
    upd = write_update(tmp_path, rows)
    cfg = make_cfg(tmp_path, updates=[upd])
    with pytest.raises(ValueError, match="parent_name disagrees"):
        s2._load_updates(cfg)


def test_nonnumeric_value_rejected(tmp_path):
    rows = valid_rows().assign(value="n/a")
    upd = write_update(tmp_path, rows)
    cfg = make_cfg(tmp_path, updates=[upd])
    with pytest.raises(ValueError, match="non-numeric"):
        s2._load_updates(cfg)
