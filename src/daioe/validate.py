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


@dataclass
class PctlTieResult:
    """Outcome of a tie-aware percentile-rank comparison for one column.

    A percentile rank is only well-defined up to ties: when several rows share the same
    RANKED VALUE within a ``by`` group, Stata's ``pctl_rank`` program assigns them a block
    of consecutive ranks whose ORDER depends on Stata's (unstable, quicksort) ``sort``.
    The within-tie permutation is therefore non-reproducible, but two invariants are not:

      * a row whose ranked value is UNIQUE within its (by, value) group must receive the
        same percentile rank as the reference, exactly (within ``tol``); and
      * within any tie block (>=2 rows sharing the same by+value), the MULTISET of assigned
        percentile ranks must be identical between produced and reference.

    Checking both invariants is STRICTER than eyeballing: a genuine ranking error on a
    non-tied row, or a corrupted tie block (a rank swapped for a value that does not belong
    to the block), fails the check; only the irreducible within-tie order is tolerated.
    """
    col: str
    value_col: str
    passed: bool
    n_rows: int = 0
    n_nontie: int = 0
    n_tie_blocks: int = 0
    nan_mismatch: int = 0
    strict_mismatch: int = 0           # non-tied rows whose rank differs from ref
    tie_block_mismatch: int = 0        # tie blocks whose multiset differs from ref
    worst_strict: list[tuple[Any, float]] = field(default_factory=list)
    worst_blocks: list[tuple[Any, float]] = field(default_factory=list)
    gate_msgs: list[str] = field(default_factory=list)


def compare_pctl_tie_aware(
    got: pd.DataFrame,
    ref_path: str | Path,
    keys: list[str],
    pctl_col: str,
    value_col: str,
    by: str = "year",
    tol: float = 1e-6,
    name: str = "",
    worst_n: int = 5,
) -> PctlTieResult:
    """Tie-aware comparison of a percentile-rank column against a Stata reference.

    ``pctl_col`` is the rank, ``value_col`` is the variable it was ranked on (e.g.
    ``pctl_rank_allapps`` <- ``exp_cumul_allapps``; ``pctl_rank_genai`` <- ``daioe_genai``).
    Ranks are formed WITHIN each ``by`` group (Stata ``sort year value`` then ``by year:``);
    rows are grouped into tie blocks on (``by``, ranked ``value``).

    The check, after aligning ``got`` and ``ref`` on ``keys``:

      1. NaN masks of ``pctl_col`` must match (a missing rank must stay missing).
      2. For every row whose ranked value is NON-tied within its (by, value) group, the
         produced rank must equal the reference rank within ``tol`` (STRICT: catches any
         real ranking error on a uniquely-valued row).
      3. For every tie block (>=2 rows with equal by+value), the SORTED MULTISET of produced
         ranks must equal the sorted multiset of reference ranks within ``tol`` (the only
         freedom granted is the unreproducible within-tie permutation).

    Returns a :class:`PctlTieResult`; ``passed`` is True iff there are no NaN-mask, strict,
    or tie-block multiset mismatches. Before partitioning, the ranked ``value_col`` is
    required to AGREE between ``got`` and ``ref`` (NaN mask and values within ``tol``); this
    makes the tie partition well-defined on both sides rather than trusting ``got`` alone, so
    a corrupted produced value column cannot fabricate or hide a tie. In the pipeline the
    value columns are independently validated bit-exact via :func:`compare_to_dta`, so this
    gate normally passes; it keeps the check self-contained if ever run in isolation.
    """
    ref = read_dta(ref_path)
    name = name or f"{pctl_col}<-{value_col}"
    res = PctlTieResult(col=pctl_col, value_col=value_col, passed=True)

    # gate: structural
    if len(got) != len(ref):
        res.passed = False
        res.gate_msgs.append(f"row-count mismatch: got {len(got)} vs ref {len(ref)}")
        return res
    for need, side, frame in ((pctl_col, "got", got), (pctl_col, "ref", ref),
                              (value_col, "got", got), (value_col, "ref", ref),
                              (by, "got", got), (by, "ref", ref)):
        if need not in frame.columns:
            res.passed = False
            res.gate_msgs.append(f"column '{need}' missing on {side}")
    if not res.passed:
        return res

    # align on keys (same stable sort as compare_to_dta)
    g, r, amsgs = _align(got, ref, keys)
    res.gate_msgs.extend(amsgs)
    if amsgs:
        res.passed = False
        return res

    res.n_rows = len(g)
    gp = pd.to_numeric(g[pctl_col], errors="coerce").to_numpy()
    rp = pd.to_numeric(r[pctl_col], errors="coerce").to_numpy()

    # gate 1: NaN masks of the rank column
    gnan, rnan = np.isnan(gp), np.isnan(rp)
    res.nan_mismatch = int((gnan != rnan).sum())
    if res.nan_mismatch:
        res.passed = False

    # gate 1b: the ranked value column must AGREE between got and ref, so the tie partition
    # is well-defined on BOTH sides rather than trusted from got alone. The value columns are
    # validated bit-exact separately, so this normally passes; it closes the theoretical gap
    # where a corrupted produced value column could fabricate or hide a tie.
    gval = pd.to_numeric(g[value_col], errors="coerce").to_numpy()
    rval = pd.to_numeric(r[value_col], errors="coerce").to_numpy()
    v_nan_mismatch = int((np.isnan(gval) != np.isnan(rval)).sum())
    both_v = ~np.isnan(gval) & ~np.isnan(rval)
    v_max = float(np.max(np.abs(gval[both_v] - rval[both_v]))) if both_v.any() else 0.0
    if v_nan_mismatch or v_max > tol:
        res.passed = False
        res.gate_msgs.append(
            f"ranked value '{value_col}' disagrees between got and ref "
            f"(nan_mismatch={v_nan_mismatch}, max|diff|={v_max:.2e}); tie partition undefined"
        )
        return res

    # tie partition: group on (by, ranked value). Both sides agree on the value (gated above),
    # so the partition is identical on got and ref. Stata ranks within a 'by' group, and
    # missing-by rows are ranked together as their own group (mirrored upstream by mapping a
    # missing year to a sentinel), so a missing 'by' is treated as a single group here too.
    by_g = pd.to_numeric(g[by], errors="coerce").to_numpy()
    val_g = gval
    by_key = np.where(np.isnan(by_g), -np.inf, by_g)
    # round the ranked value to collapse float-noise into genuine ties (exact equality is
    # what Stata's sort sees; the value columns are bit-exact, so rounding to 1e-9 is safe).
    val_key = np.where(np.isnan(val_g), np.nan, np.round(val_g, 9))

    part = pd.DataFrame({
        "by": by_key,
        "val": val_key,
        "gp": gp,
        "rp": rp,
        "rowpos": np.arange(len(g)),
    })
    # only rows that actually received a rank participate (both sides non-missing already
    # gated above for mask equality; rank-bearing rows are the non-missing value rows).
    ranked = part[~np.isnan(part["gp"].to_numpy()) & ~np.isnan(part["val"].to_numpy())]

    strict_bad: list[tuple[Any, float]] = []
    block_bad: list[tuple[Any, float]] = []
    n_nontie = 0
    n_blocks = 0
    key_frame = g[keys].reset_index(drop=True)

    for (_b, _v), sub in ranked.groupby(["by", "val"], sort=False):
        if len(sub) == 1:
            n_nontie += 1
            gv = float(sub["gp"].iloc[0])
            rv = float(sub["rp"].iloc[0])
            d = abs(gv - rv)
            if d > tol:
                kpos = int(sub["rowpos"].iloc[0])
                strict_bad.append((tuple(key_frame.iloc[kpos].tolist()), d))
        else:
            n_blocks += 1
            gset = np.sort(sub["gp"].to_numpy())
            rset = np.sort(sub["rp"].to_numpy())
            if gset.shape != rset.shape:
                worst = float("inf")
            else:
                worst = float(np.max(np.abs(gset - rset))) if gset.size else 0.0
            if not np.isfinite(worst) or worst > tol:
                # representative key (first row in the block) for reporting
                kpos = int(sub["rowpos"].iloc[0])
                block_bad.append((tuple(key_frame.iloc[kpos].tolist()), worst))

    res.n_nontie = n_nontie
    res.n_tie_blocks = n_blocks
    res.strict_mismatch = len(strict_bad)
    res.tie_block_mismatch = len(block_bad)
    res.worst_strict = sorted(strict_bad, key=lambda t: -t[1])[:worst_n]
    res.worst_blocks = sorted(block_bad, key=lambda t: -t[1])[:worst_n]

    if res.strict_mismatch or res.tie_block_mismatch:
        res.passed = False
    return res


def render_pctl_report(results: list[PctlTieResult], title: str = "DAIOE pctl tie-aware") -> str:
    """Render tie-aware percentile-rank results as a markdown table."""
    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"# {title}", f"_generated {ts}_", ""]
    n_pass = sum(r.passed for r in results)
    lines.append(f"**{n_pass}/{len(results)} pctl columns pass the tie-aware check.**")
    lines.append("")
    lines.append("| column | <- value | non-tie | tie blocks | strict-mismatch | "
                 "block-mismatch | nan-mismatch |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in results:
        flag = "" if r.passed else " ⚠️"
        lines.append(
            f"| {r.col}{flag} | {r.value_col} | {r.n_nontie} | {r.n_tie_blocks} | "
            f"{r.strict_mismatch} | {r.tie_block_mismatch} | {r.nan_mismatch} |"
        )
    return "\n".join(lines)


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


def write_pctl_report(
    results: list["PctlTieResult"], reports_dir: str | Path, title: str = "DAIOE pctl tie-aware"
) -> Path:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = reports_dir / f"validation_pctl_{ts}.md"
    path.write_text(render_pctl_report(results, title=title), encoding="utf-8")
    return path
