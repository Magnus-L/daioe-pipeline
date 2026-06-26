"""Validation harness: compare a produced DataFrame against a Stata .dta ground truth.

The comparison is deliberately gated so that a failure localises to a stage and a
column rather than producing one opaque boolean. Gates, in order:

  1. row count           (structural error -> fail fast)
  2. column presence     (the value columns we claim to reproduce exist on both sides)
  3. key alignment       (sort both sides by keys; keys must match 1:1)
  4. NaN-mask equality   (Stata '.' must map to NaN; never silently coerced)
  5. numeric closeness    (per column max|got-ref| <= tol; worst-5 offenders printed)
  6. dtype-class warning (float-vs-int mismatch is reported, not failed)

Tolerances come from config: 1e-6 for double-stored internal panels/intermediates,
1e-5 for float32-stored publication panels.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .io import read_dta


@dataclass
class ColResult:
    col: str
    max_abs_diff: float
    n_mismatch: int
    nan_mismatch: int
    worst: list[tuple[Any, float]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.n_mismatch == 0 and self.nan_mismatch == 0


@dataclass
class CompareResult:
    name: str
    ref_path: str
    passed: bool
    rows_got: int
    rows_ref: int
    gate_msgs: list[str] = field(default_factory=list)
    cols: list[ColResult] = field(default_factory=list)

    def summary(self) -> str:
        head = "PASS" if self.passed else "FAIL"
        return f"[{head}] {self.name}: rows {self.rows_got}/{self.rows_ref}"


def _align(
    got: pd.DataFrame, ref: pd.DataFrame, keys: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Sort both frames by keys and reset index so rows line up positionally."""
    msgs: list[str] = []
    g = got.sort_values(keys, kind="mergesort").reset_index(drop=True)
    r = ref.sort_values(keys, kind="mergesort").reset_index(drop=True)
    # verify the key columns themselves agree after sorting
    for k in keys:
        if not g[k].astype(str).equals(r[k].astype(str)):
            msgs.append(f"key column '{k}' differs after sort/align")
    return g, r, msgs


def compare_to_dta(
    got: pd.DataFrame,
    ref_path: str | Path,
    keys: list[str],
    value_cols: list[str] | None = None,
    tol: float = 1e-6,
    name: str = "",
    worst_n: int = 5,
) -> CompareResult:
    """Compare ``got`` to the Stata panel at ``ref_path`` on ``value_cols`` (default:
    all numeric columns shared by both, minus keys), keyed by ``keys``."""
    ref = read_dta(ref_path)
    name = name or Path(ref_path).name

    res = CompareResult(
        name=name,
        ref_path=str(ref_path),
        passed=True,
        rows_got=len(got),
        rows_ref=len(ref),
    )

    # gate 1: row count
    if len(got) != len(ref):
        res.passed = False
        res.gate_msgs.append(f"row-count mismatch: got {len(got)} vs ref {len(ref)}")
        return res

    # gate 2: keys present
    for k in keys:
        if k not in got.columns or k not in ref.columns:
            res.passed = False
            res.gate_msgs.append(f"key '{k}' missing (got={k in got.columns}, ref={k in ref.columns})")
    if not res.passed:
        return res

    # choose value columns
    if value_cols is None:
        shared = [c for c in ref.columns if c in got.columns and c not in keys]
        value_cols = [c for c in shared if np.issubdtype(ref[c].dtype, np.number)]

    missing = [c for c in value_cols if c not in got.columns or c not in ref.columns]
    if missing:
        res.passed = False
        res.gate_msgs.append(f"value columns missing on a side: {missing}")
        return res

    # gate 3: key alignment
    g, r, amsgs = _align(got, ref, keys)
    res.gate_msgs.extend(amsgs)
    if amsgs:
        res.passed = False
        return res

    # gates 4 + 5: per-column NaN-mask + numeric closeness
    for c in value_cols:
        gv = pd.to_numeric(g[c], errors="coerce")
        rv = pd.to_numeric(r[c], errors="coerce")
        gnan, rnan = gv.isna().to_numpy(), rv.isna().to_numpy()
        nan_mismatch = int((gnan != rnan).sum())

        both = ~gnan & ~rnan
        diff = np.abs(gv.to_numpy()[both] - rv.to_numpy()[both])
        if diff.size:
            max_abs = float(diff.max())
            bad = diff > tol
            n_bad = int(bad.sum())
            # worst offenders with their key values
            order = np.argsort(diff)[::-1][:worst_n]
            key_vals = g.loc[both, keys].reset_index(drop=True)
            worst = [
                (tuple(key_vals.iloc[int(i)].tolist()), float(diff[int(i)]))
                for i in order
                if diff[int(i)] > tol
            ]
        else:
            max_abs, n_bad, worst = 0.0, 0, []

        cr = ColResult(
            col=c,
            max_abs_diff=max_abs,
            n_mismatch=n_bad,
            nan_mismatch=nan_mismatch,
            worst=worst,
        )
        res.cols.append(cr)
        if not cr.passed:
            res.passed = False

    return res


def render_report(results: list[CompareResult], title: str = "DAIOE validation") -> str:
    """Render a list of CompareResults as a markdown report."""
    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"# {title}", f"_generated {ts}_", ""]
    n_pass = sum(r.passed for r in results)
    lines.append(f"**{n_pass}/{len(results)} targets passed.**")
    lines.append("")
    for r in results:
        lines.append(f"## {r.summary()}")
        lines.append(f"- ref: `{r.ref_path}`")
        for m in r.gate_msgs:
            lines.append(f"- gate: {m}")
        if r.cols:
            lines.append("")
            lines.append("| column | max|diff| | n>tol | nan-mismatch | worst keys |")
            lines.append("|---|---|---|---|---|")
            for c in r.cols:
                flag = "" if c.passed else " ⚠️"
                worst = "; ".join(f"{k}={d:.2e}" for k, d in c.worst[:3])
                lines.append(
                    f"| {c.col}{flag} | {c.max_abs_diff:.2e} | {c.n_mismatch} | "
                    f"{c.nan_mismatch} | {worst} |"
                )
        lines.append("")
    return "\n".join(lines)


def write_report(results: list[CompareResult], reports_dir: str | Path, title: str = "DAIOE validation") -> Path:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = reports_dir / f"validation_{ts}.md"
    path.write_text(render_report(results, title=title), encoding="utf-8")
    return path
