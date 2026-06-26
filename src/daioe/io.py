"""Readers and writers.

One fixed Stata reader is used for BOTH inputs and validation targets so that dtype
handling is identical on both sides of a comparison. We standardise on pyreadstat,
which reads a Stata ``.dta`` into float64 (a float32-stored publication value is
widened to its exact float32 representation), avoiding the pandas ``read_stata``
quirk of returning float32 for some files and float64 for others.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyreadstat


# ----------------------------------------------------------------------------- read
def read_dta(path: str | Path) -> pd.DataFrame:
    """Read a Stata .dta into a DataFrame (float64), discarding pyreadstat metadata."""
    df, _meta = pyreadstat.read_dta(str(path))
    return df


def read_dta_meta(path: str | Path):
    """Read a .dta returning (df, meta) when value labels / column labels are needed."""
    return pyreadstat.read_dta(str(path))


def read_csv_tab(path: str | Path) -> pd.DataFrame:
    """Read a Stata-style tab-delimited export."""
    return pd.read_csv(path, sep="\t")


def read_excel_sheet(path: str | Path, sheet: str | int = 0) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet)


# ---------------------------------------------------------------------------- write
def write_dta(df: pd.DataFrame, path: str | Path) -> None:
    """Write a .dta. Caller is responsible for any float32 down-cast (publication)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    # pandas to_stata is convenient for labelling; version 118 supports UTF-8.
    df.to_stata(str(path), write_index=False, version=118)


def write_csv_tab(df: pd.DataFrame, path: str | Path) -> None:
    """Write a TAB-delimited CSV, mirroring Stata ``export delimited, delimiter(tab)``."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, sep="\t", index=False)


def write_xlsx(df: pd.DataFrame, path: str | Path, sheet: str = "DAIOE") -> None:
    """Write an .xlsx with a single sheet (default name mirrors the Stata export)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, sheet_name=sheet, index=False)


def cast_publication(df: pd.DataFrame, float32_cols: list[str]) -> pd.DataFrame:
    """Down-cast the named columns to float32 so .dta storage matches the publication
    panels (Stata stores daioe_* and year as float). Returns a copy."""
    out = df.copy()
    for c in float32_cols:
        if c in out.columns:
            out[c] = out[c].astype("float32")
    return out


def write_outputs(
    df: pd.DataFrame,
    stem: str,
    out_dir: str | Path,
    formats: list[str],
    sheet: str = "DAIOE",
) -> list[Path]:
    """Write ``df`` as <stem>.<fmt> for each requested format. Returns the paths."""
    out_dir = Path(out_dir)
    written: list[Path] = []
    for fmt in formats:
        p = out_dir / f"{stem}.{fmt}"
        if fmt == "dta":
            write_dta(df, p)
        elif fmt == "csv":
            write_csv_tab(df, p)
        elif fmt == "xlsx":
            write_xlsx(df, p, sheet=sheet)
        else:
            raise ValueError(f"unknown export format: {fmt}")
        written.append(p)
    return written
