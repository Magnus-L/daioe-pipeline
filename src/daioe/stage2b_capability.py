"""Stage 2b: the human-anchored capability transform, behind a validation gate.

Design and evidence: ``notes/DESIGN-capability-transform_2026-08-07.md``. The mechanics were
written and validated on 7 Aug 2026 in ``scripts/capability_transform_20260807.py``, which
stays as the exhibit that produced the design note's tables; this module is the same
arithmetic moved into the package so the pipeline can run it, and that script now imports
from here rather than keeping a second copy.

WHY IT IS A STAGE NOW, AND WHY IT IS GATED. The published construction scales every
benchmark by a logarithm referenced to the metric's *scale ceiling*, which diverges as the
ceiling nears: 58 per cent of recorded 2023 progress comes from metrics within ten per cent
of their ceiling, against 7 per cent in 2015. That was already a defect worth fixing. What
made it urgent is METR (``notes/EXTENSION-agentic-metr_2026-08-13.md``): its 2025 increment
is 2.2051 in ln(minutes), an order of magnitude above every other application, so under the
raw construction one series would move the composite more than the other eight together.
Under this transform the same series is well-behaved (theta = -1.003, w = 0.196) and the
interim TheAgentCompany series is revealed as uninformative (weight share 2.5e-06) rather
than merely suspected of it. The agentic switch therefore cannot ship before this lands,
which is why it is wired in rather than left as a script.

    theta_bt = human-referenced log-distance of the frontier (direction-aware, see _theta)
    pi_bt    = sigma(alpha * theta_bt)      pseudo-item-response, "clears the human bar"
    w_bt     = pi (1 - pi)                  Fisher information
    Dp_it    = sum_b w_bar d_theta / sum_b w_bar    progress, weighted CHANGES not levels
    se(C_it) = 1 / sqrt(sum_b w)            explodes when the basket saturates

THE GATE. Enabling a second construction of the same measure is exactly the kind of change
that should have to prove itself on every run rather than once in a note. Five cheap checks
run whenever the stage runs, each one a property the design note claims:

  1. anchor_coverage      the transform is only as good as its anchors; a published-category
                          application with none cannot be transformed at all (image
                          generation was at 0 per cent before the sourcing work).
  2. no_negative_progress the weighted-CHANGES form exists because differencing an
                          application-level weighted mean produced negative progress in five
                          application-years. Any negative value means that property broke.
  3. finite_information   theta finite, pi strictly inside (0, 1), w > 0. A degenerate anchor
                          silently zeroes a series' weight, which is what makes
                          TheAgentCompany's 100.0 ceiling uninformative; the gate reports the
                          weakest series rather than letting it pass unnoticed.
  4. monotone_frontier    theta is a running max by construction, so a decrease means the
                          direction logic is wrong for that scale family. This is the defect
                          class the frozen `threshold` column actually had.
  5. alpha_stability      alpha is the one free parameter. The design note gridded it over a
                          sixteen-fold range and found the occupational ordering fixed; the
                          gate re-checks the cheap half of that claim (application-year
                          progress ranks) on the current basket, so a future basket that
                          makes alpha load-bearing is caught rather than assumed away.

The occupational half of check 5, and the published-vs-capability comparison, need stages 3
to 5 and stay in the design note's grid rather than running on every invocation.

FAILING THE GATE DOES NOT FAIL THE PIPELINE unless the transform is being consumed. With
``capability_transform.enabled: false`` (the default) the stage is diagnostic: it writes its
panels and reports gate status, and stage 4 continues to consume the published Delta p. That
is deliberate. The transform is a documented robustness variant until Erik's anchor
convention is settled (decision 4, 15 Aug), and a gate that blocks a run nobody asked to
change would be theatre.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# The one anchor whose units disagree with its values: human top-5 error is 5.1 per cent,
# recorded as the fraction 0.051 while the values were multiplied by 100 by the Top-5
# override. See the design note, defect 2.
ANCHOR_FIX = {"Imagenet Image Recognition": 5.1}
ANCHOR_FILE = "human_anchors_v1.csv"

# alpha grid for the stability gate: the sixteen-fold range the design note reports.
ALPHA_GRID = (0.25, 0.5, 1.0, 2.0, 4.0)


def load_sourced_anchors(cfg) -> dict[str, float]:
    """Anchors sourced for metrics the frozen sheet leaves unanchored.

    Every row carries its source and a verbatim supporting quote; the file is the evidence,
    not a lookup of convenience.
    """
    path = cfg.path("derived") / ANCHOR_FILE
    if not path.exists():
        return {}
    a = pd.read_csv(path)
    return dict(zip(a["metrics_name"], a["anchor"].astype(float)))


def _signed_log(x: np.ndarray) -> np.ndarray:
    """ln(x) for x>0, -ln(-x) for x<0, 0 at zero.

    The frozen construction's own convention for the Score family (online appendix Table,
    "Score<0", "Score=0", "Score>0"), kept because Atari scores go negative: Pong runs from
    -21 to +21.
    """
    x = np.asarray(x, dtype=float)
    return np.where(x > 0, np.log(np.abs(np.where(x > 0, x, 1.0))),
           np.where(x < 0, -np.log(np.abs(np.where(x < 0, x, 1.0))), 0.0))


def _theta(scale: str, v: np.ndarray, h: float) -> np.ndarray:
    """Human-referenced log-distance. Zero at parity, positive above, negative below."""
    if scale == "Percentage correct":                       # log-odds of accuracy vs human
        p = np.clip(v / 100.0, 1e-6, 1 - 1e-6)
        ph = np.clip(h / 100.0, 1e-6, 1 - 1e-6)
        return np.log(p / (1 - p)) - np.log(ph / (1 - ph))
    if scale in ("Percentage error", "FID", "Perplexity"):   # log error ratio, human / machine
        return np.log(max(h, 1e-9)) - np.log(np.clip(v, 1e-9, None))
    if scale == "Model Entropy":                             # bits -> log perplexity ratio
        return (h - v) * np.log(2.0)
    if scale in ("Score", "ELO rating", "BLEU score"):        # signed log ratio, machine / human
        return _signed_log(v) - _signed_log(np.array(h))
    raise ValueError(f"_theta: unhandled scale {scale!r}")


def build_capability(cfg, alpha: float = 1.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (per-benchmark-year capability, per-application-year capability + s.e.).

    ``alpha`` is the discrimination slope, the analogue of delta in the social discount. It
    sets how sharply the information weight concentrates around the human anchor: alpha -> 0
    weights every benchmark nearly equally and approaches the published unweighted treatment,
    while large alpha counts only benchmarks close to parity. Gridded like delta; alpha = 1
    is the neutral default and the design note shows nothing the paper uses moves over a
    sixteen-fold range.
    """
    fd = pd.read_parquet(cfg.out_file("formated_data.parquet"))
    sourced = load_sourced_anchors(cfg)
    # fill in the anchors the frozen sheet lacks, then apply the units erratum
    fd["target"] = fd["target"].fillna(fd["metrics_name"].map(sourced))
    fd["target"] = fd.apply(lambda r: ANCHOR_FIX.get(r["metrics_name"], r["target"]), axis=1)
    fd = fd[fd["value"].notna() & fd["target"].notna()].copy()

    out = []
    for (m, sc, app), g in fd.groupby(["metrics_name", "scale", "parent_name"]):
        g = g.sort_values("date")
        th = _theta(sc, g["value"].to_numpy(float), float(g["target"].iloc[0]))
        # the frontier in capability terms is the running max of theta, direction-correct
        # for every scale family by construction
        g = g.assign(theta=np.maximum.accumulate(th))
        yr = g.groupby("year")["theta"].max().reset_index()
        yr["metrics_name"], yr["parent_name"], yr["scale"] = m, app, sc
        out.append(yr)
    bench = pd.concat(out, ignore_index=True)

    # carry each benchmark's frontier forward across its observed span, so a year with no
    # new result contributes its standing capability rather than dropping out
    spans = []
    for (m, app), g in bench.groupby(["metrics_name", "parent_name"]):
        full = pd.DataFrame({"year": np.arange(int(g["year"].min()), int(g["year"].max()) + 1)})
        full = full.merge(g, on="year", how="left")
        full[["metrics_name", "parent_name"]] = m, app
        full["theta"] = full["theta"].ffill()
        full["scale"] = full["scale"].ffill().bfill()
        spans.append(full)
    bench = pd.concat(spans, ignore_index=True)

    bench["pi"] = 1.0 / (1.0 + np.exp(-alpha * bench["theta"]))
    bench["w"] = bench["pi"] * (1.0 - bench["pi"])

    # --- progress: information-weighted mean of WITHIN-benchmark changes -----------------
    # Differencing an application-level weighted mean would make progress move whenever a
    # benchmark enters or leaves, because setting every difficulty at its own human anchor
    # assumes parity on VQA and parity on ImageNet are the same capability level, which they
    # are not. Weighting the changes instead never compares two different baskets, so it is
    # composition-neutral by construction.
    bench = bench.sort_values(["metrics_name", "year"])
    bench["d_theta"] = bench.groupby("metrics_name")["theta"].diff()
    bench["w_lag"] = bench.groupby("metrics_name")["w"].shift(1)
    bench["w_bar"] = 0.5 * (bench["w"] + bench["w_lag"])   # information over the interval

    def agg(g):
        gg = g.dropna(subset=["d_theta"])
        wsum = gg["w_bar"].sum()
        info = g["w"].sum()
        return pd.Series(
            {
                "delta_p": np.average(gg["d_theta"], weights=gg["w_bar"]) if wsum > 0 else np.nan,
                "capability": np.average(g["theta"], weights=g["w"]) if info > 0 else np.nan,
                "info": info,
                "se": 1.0 / np.sqrt(info) if info > 0 else np.inf,
                "n_anchored": len(g),
            }
        )

    app = bench.groupby(["parent_name", "year"]).apply(agg).reset_index()
    return bench, app.sort_values(["parent_name", "year"])


# --------------------------------------------------------------------------- the gate ---
@dataclass
class Gate:
    """One declared property, checked. ``detail`` is what a reader needs to act on it."""

    name: str
    passed: bool
    detail: str

    def summary(self) -> str:
        return f"[{'PASS' if self.passed else 'FAIL'}] capability::{self.name}: {self.detail}"


@dataclass
class CapabilityResult:
    bench: pd.DataFrame
    app: pd.DataFrame
    gates: list[Gate] = field(default_factory=list)
    enabled: bool = False

    @property
    def passed(self) -> bool:
        return all(g.passed for g in self.gates)


def _gate_anchor_coverage(cfg, bench: pd.DataFrame, min_share: float) -> Gate:
    fr = pd.read_parquet(cfg.out_file("metrics_frontiers.parquet"))
    observed = fr.groupby("parent_name")["metrics_name"].nunique()
    anchored = bench.groupby("parent_name")["metrics_name"].nunique()
    cover = pd.concat([observed.rename("observed"), anchored.rename("anchored")], axis=1).fillna(0)
    cover["share"] = cover["anchored"] / cover["observed"]
    overall = cover["anchored"].sum() / cover["observed"].sum()
    # An application in the publication categories with no anchored metric cannot be
    # transformed at all, which is a different failure from thin coverage.
    empty = sorted(cover.index[cover["anchored"] == 0])
    ok = (overall >= min_share) and not empty
    worst = cover["share"].idxmin()
    detail = (
        f"{int(cover['anchored'].sum())}/{int(cover['observed'].sum())} metrics anchored "
        f"({overall:.1%}, floor {min_share:.0%}); weakest application {worst!r} at "
        f"{cover.loc[worst, 'share']:.0%}"
    )
    if empty:
        detail += f"; UNANCHORED APPLICATIONS: {empty}"
    return Gate("anchor_coverage", ok, detail)


def _gate_no_negative_progress(app: pd.DataFrame) -> Gate:
    d = app["delta_p"].dropna()
    neg = d[d < -1e-9]
    return Gate(
        "no_negative_progress",
        neg.empty,
        f"{len(neg)} of {len(d)} application-years negative"
        + (f"; worst {neg.min():.4f}" if not neg.empty else ""),
    )


def _gate_finite_information(bench: pd.DataFrame) -> Gate:
    bad_theta = (~np.isfinite(bench["theta"].to_numpy(float))).sum()
    bad_w = (~(bench["w"] > 0)).sum()
    # The weakest live series is reported whether or not the gate fails: a weight this small
    # means the series is present in the basket and contributing nothing, which is a
    # measurement about its anchor, not about the transform.
    per_series = bench.groupby("metrics_name")["w"].max().sort_values()
    weakest = per_series.index[0]
    ok = bad_theta == 0 and bad_w == 0
    return Gate(
        "finite_information",
        ok,
        f"{bad_theta} non-finite theta, {bad_w} non-positive weights; least informative "
        f"series {weakest!r} at max w = {per_series.iloc[0]:.2e}",
    )


def _gate_monotone_frontier(bench: pd.DataFrame) -> Gate:
    d = bench.dropna(subset=["d_theta"])
    drops = d[d["d_theta"] < -1e-9]
    detail = f"{len(drops)} of {len(d)} benchmark-years fall"
    if not drops.empty:
        s = drops.groupby("scale").size().to_dict()
        detail += f"; by scale family {s}"
    return Gate("monotone_frontier", drops.empty, detail)


def _gate_alpha_stability(cfg, alpha: float, min_rho: float) -> Gate:
    """alpha is the one free parameter; check the current basket does not make it matter.

    Measured against the configured alpha, because that is what ships, and enforced over the
    OPERATIONAL band only, a four-fold excursion either side of it. Beyond that band alpha
    stops being a robustness excursion and becomes a different weighting choice: at alpha = 4
    only benchmarks near parity count at all. The wider grid is still computed and reported,
    because seeing where the object does start to move is the point of gridding it.

    Note what this is not. The design note's claim is that nothing the PAPER uses moves over
    a sixteen-fold range, and it evidences that with the occupational ordering (Spearman
    >= 0.9927), which needs stages 3 to 5 and stays in the note. This gate checks the cheap
    and stricter object, the rank order of application-year progress that stage 4 consumes.
    It moves more than the occupational ordering does, which is expected: the design note's
    own finding is that cross-occupation content comes from the O*NET profile and the mapping
    matrix rather than from the benchmark series.
    """
    band = (alpha / 4.0, alpha * 4.0)
    grid = sorted({*ALPHA_GRID, alpha})
    _, ref_ap = build_capability(cfg, alpha=alpha)
    ref = ref_ap.set_index(["parent_name", "year"])["delta_p"]

    rhos: dict[float, float] = {}
    for a in grid:
        if a == alpha:
            continue
        _, ap = build_capability(cfg, alpha=a)
        joined = pd.concat(
            [ref, ap.set_index(["parent_name", "year"])["delta_p"]], axis=1, keys=["ref", "alt"]
        ).dropna()
        rhos[a] = stats.spearmanr(joined["ref"], joined["alt"]).statistic

    enforced = {a: r for a, r in rhos.items() if band[0] <= a <= band[1]}
    worst = min(enforced.values()) if enforced else 1.0
    outside = {a: r for a, r in rhos.items() if a not in enforced}
    detail = (
        f"progress-rank correlation vs alpha={alpha:g} "
        f"(enforced over {band[0]:g}-{band[1]:g}, floor {min_rho:.2f}): "
        + ", ".join(f"{a:g}:{r:.4f}" for a, r in sorted(enforced.items()))
    )
    if outside:
        detail += "; reported only: " + ", ".join(f"{a:g}:{r:.4f}" for a, r in sorted(outside.items()))
    return Gate("alpha_stability", worst >= min_rho, detail)


def run(cfg, validate: bool = True) -> CapabilityResult:
    """Build the capability panels, check the gate, and write the checkpoints.

    Returns the panels and the gate results. Stage 4 consumes the published Delta p unless
    ``capability_transform.enabled`` is true, so with the default config this stage is a
    diagnostic that costs one pass over the frontier data and answers, every run, whether
    the transform would be safe to consume.
    """
    conf = dict(cfg.raw.get("capability_transform") or {})
    enabled = bool(conf.get("enabled", False))
    alpha = float(conf.get("alpha", 1.0))
    min_share = float(conf.get("min_anchor_coverage", 0.65))
    min_rho = float(conf.get("min_alpha_rho", 0.95))

    bench, app = build_capability(cfg, alpha=alpha)
    bench.to_parquet(cfg.out_file("capability_benchmarks.parquet"), index=False)
    app.to_parquet(cfg.out_file("capability_applications.parquet"), index=False)

    gates: list[Gate] = []
    if validate:
        gates = [
            _gate_anchor_coverage(cfg, bench, min_share),
            _gate_no_negative_progress(app),
            _gate_finite_information(bench),
            _gate_monotone_frontier(bench),
            _gate_alpha_stability(cfg, alpha, min_rho),
        ]
        for g in gates:
            print(g.summary())

    res = CapabilityResult(bench=bench, app=app, gates=gates, enabled=enabled)
    if enabled and validate and not res.passed:
        raise SystemExit(
            "capability transform is ENABLED and its gate failed; refusing to let stage 4 "
            "consume it. Fix the failing property or set capability_transform.enabled: false "
            "to keep it diagnostic."
        )
    return res
