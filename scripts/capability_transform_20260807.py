#!/usr/bin/env python3
"""Human-anchored capability transform: the reduced form of an item-response model.

Built 7 August 2026 after Magnus agreed the design direction. Companion note:
``notes/DESIGN-capability-transform_2026-08-07.md``.

WHY. The published construction scales every benchmark by a logarithm referenced to the
metric's *scale ceiling* (``-ln((100-v)/100)`` and friends), which diverges as the ceiling
nears. Empirically 58 per cent of recorded 2023 progress now comes from metrics within ten
per cent of their ceiling, against 7 per cent in 2015. The paper's own stated rationale is
the opposite of this behaviour: it says the rescaling "captures diminishing marginal gains
in AI advancements as they approach human-level proficiency".

THE FORM. Epoch's Capabilities Index (Rosetta Stone, arXiv 2512.00193) solves the same
problem with a two-parameter item-response model, performance = sigma(alpha_b [C_m - D_b]).
A benchmark is informative about capability only near its own difficulty, so a saturated
benchmark stops contributing automatically, with no retirement rule. We cannot estimate
that model retrospectively: only 12 of 712 models in the frozen basket appear in two or
more applications, so nothing links the applications onto a common latent scale.

We therefore substitute the *declared human anchor* for the crossing structure. Each
benchmark's difficulty is set at human performance, which puts every benchmark on a common
human-referenced scale by construction and makes basket composition second-order.

  theta_bt = human-referenced log-distance of the frontier (direction-aware, see _theta)
  pi_bt    = sigma(theta_bt)              pseudo-item-response: "clears the human bar"
  w_bt     = pi (1 - pi)                  Fisher information at alpha = 1
  C_it     = sum_b w theta / sum_b w      application capability level
  se(C_it) = 1 / sqrt(sum_b w)            explodes when the basket saturates
  Dp_it    = C_it - C_i,t-1               progress, the input Stage 4 consumes

The information weight is what does the work: near the ceiling theta grows without bound
but w vanishes at exactly the compensating rate, so the product stays finite. Progress near
the ceiling is counted in raw points rather than in nines; progress near the human anchor is
counted proportionally. That is the S-curve, derived rather than imposed.

TWO DEFECTS IN THE SOURCE FIXED HERE, both in the frozen construction rather than the port,
and neither of which touches any published value because ``threshold`` never enters Stage 3
or later:
  1. ``threshold`` is computed as ``value >= target`` regardless of direction, so on every
     lower-is-better metric it fires on the FIRST observation, when the machine is at its
     worst. Switchboard WER fires 2011-08 and is actually beaten 2016-12.
  2. The Imagenet target is 0.051, a fraction, while its values were multiplied by 100 by
     the Top-5 override. Human top-5 error is 5.1 per cent, so the anchor is 5.1 here.

Run:  .venv/bin/python scripts/capability_transform_20260807.py
Reads data/out and data/raw; writes nothing into data/out.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from daioe import config as cfgmod, stage2_ai_progress as s2, stage4_index as s4  # noqa: E402

LOWER_IS_BETTER = {"Percentage error", "FID", "Perplexity", "Model Entropy"}
# The one anchor whose units disagree with its values (see docstring, defect 2).
ANCHOR_FIX = {"Imagenet Image Recognition": 5.1}
# Anchors sourced for metrics the frozen sheet leaves unanchored. Every row carries its
# source and the supporting quote; see data/derived/human_anchors_v1.csv.
ANCHOR_TABLE = ROOT / "data/derived/human_anchors_v1.csv"


def load_sourced_anchors() -> dict[str, float]:
    if not ANCHOR_TABLE.exists():
        return {}
    a = pd.read_csv(ANCHOR_TABLE)
    return dict(zip(a["metrics_name"], a["anchor"].astype(float)))


def _signed_log(x: np.ndarray) -> np.ndarray:
    """ln(x) for x>0, -ln(-x) for x<0, 0 at zero.

    This is the frozen construction's own convention for the Score family (online appendix
    Table, "Score<0", "Score=0", "Score>0"), and it must be kept because Atari scores go
    negative: Pong runs from -21 to +21.
    """
    x = np.asarray(x, dtype=float)
    return np.where(x > 0, np.log(np.abs(np.where(x > 0, x, 1.0))),
           np.where(x < 0, -np.log(np.abs(np.where(x < 0, x, 1.0))), 0.0))


def _theta(scale: str, v: np.ndarray, h: float) -> np.ndarray:
    """Human-referenced log-distance. Zero at parity, positive above, negative below."""
    if scale == "Percentage correct":                     # log-odds of accuracy vs human
        p = np.clip(v / 100.0, 1e-6, 1 - 1e-6)
        ph = np.clip(h / 100.0, 1e-6, 1 - 1e-6)
        return np.log(p / (1 - p)) - np.log(ph / (1 - ph))
    if scale in ("Percentage error", "FID", "Perplexity"):  # log error ratio, human / machine
        return np.log(max(h, 1e-9)) - np.log(np.clip(v, 1e-9, None))
    if scale == "Model Entropy":                           # bits -> log perplexity ratio
        return (h - v) * np.log(2.0)
    if scale in ("Score", "ELO rating", "BLEU score"):      # signed log ratio, machine / human
        return _signed_log(v) - _signed_log(np.array(h))
    raise ValueError(f"_theta: unhandled scale {scale!r}")


def build_capability(cfg, alpha: float = 1.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (per-benchmark-year capability, per-application-year capability + s.e.).

    ``alpha`` is the discrimination slope, the second calibrated parameter of the design and
    the analogue of delta in the social discount. It sets how sharply the information weight
    concentrates around the human anchor: alpha -> 0 weights every benchmark nearly equally
    and approaches the published unweighted treatment, while large alpha counts only
    benchmarks close to parity. Grid it and report it the way delta is gridded.
    """
    fd = pd.read_parquet(ROOT / "data/out/formated_data.parquet")
    sourced = load_sourced_anchors()
    # fill in the anchors the frozen sheet lacks, then apply the units erratum
    fd["target"] = fd["target"].fillna(fd["metrics_name"].map(sourced))
    fd["target"] = fd.apply(
        lambda r: ANCHOR_FIX.get(r["metrics_name"], r["target"]), axis=1
    )
    fd = fd[fd["value"].notna() & fd["target"].notna()].copy()

    out = []
    for (m, sc, app), g in fd.groupby(["metrics_name", "scale", "parent_name"]):
        g = g.sort_values("date")
        th = _theta(sc, g["value"].to_numpy(float), float(g["target"].iloc[0]))
        # the frontier in capability terms is the running max of theta, which is
        # direction-correct for every scale family by construction
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
        spans.append(full)
    bench = pd.concat(spans, ignore_index=True)

    bench["pi"] = 1.0 / (1.0 + np.exp(-alpha * bench["theta"]))
    bench["w"] = bench["pi"] * (1.0 - bench["pi"])

    # --- progress: information-weighted mean of WITHIN-benchmark changes -----------------
    # Differencing an application-level weighted mean would make progress move whenever a
    # benchmark enters or leaves, because setting every difficulty at its own human anchor
    # assumes parity on VQA and parity on ImageNet are the same capability level, which they
    # are not. Weighting the changes instead never compares two different baskets, so it is
    # composition-neutral by construction. It is also the smaller change to the published
    # architecture: the mean over benchmarks stays, the weight and the units change.
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


def main() -> None:
    pd.set_option("display.width", 200, "display.max_rows", 300)
    cfg = cfgmod.load_config(ROOT / "config.yaml")
    bench, app = build_capability(cfg)

    fr = pd.read_parquet(ROOT / "data/out/metrics_frontiers.parquet")
    cover = (
        fr.groupby("parent_name")["metrics_name"].nunique().rename("observed").to_frame()
        .join(bench.groupby("parent_name")["metrics_name"].nunique().rename("anchored"))
        .fillna(0).astype(int)
    )
    cover["share"] = (cover["anchored"] / cover["observed"] * 100).round(0)
    print("=" * 88)
    print("A. Anchor coverage: how much of each application can carry the new transform")
    print("=" * 88)
    print(cover.to_string())

    print("\n" + "=" * 88)
    print("B. Application capability level, its s.e., and the implied progress")
    print("=" * 88)
    for a in sorted(app["parent_name"].unique()):
        s = app[(app["parent_name"] == a) & app["year"].between(2010, 2023)]
        if s.empty:
            continue
        print(f"\n--- {a} ---")
        print(s[["year", "n_anchored", "capability", "se", "delta_p"]].to_string(
            index=False, float_format=lambda x: f"{x:8.3f}"))

    print("\n" + "=" * 88)
    print("C. Published progress vs capability progress, per application-year")
    print("=" * 88)
    pub = fr.groupby(["parent_name", "year"])["deltafinal"].mean().rename("published").reset_index()
    cmp = pub.merge(app[["parent_name", "year", "delta_p", "se"]], on=["parent_name", "year"])
    cmp = cmp[cmp["year"].between(2010, 2023)]
    both = cmp.dropna(subset=["published", "delta_p"])
    print(f"application-years compared: {len(both)}")
    print(f"rank correlation of the two progress series: "
          f"{stats.spearmanr(both['published'], both['delta_p']).statistic:.4f}")
    print(f"negative capability progress (basket-composition artefacts): "
          f"{(both['delta_p'] < -1e-9).sum()} of {len(both)}")
    print("\nby year, summed across applications:")
    print(both.groupby("year")[["published", "delta_p"]].sum().to_string(
        float_format=lambda x: f"{x:9.3f}"))
    return app, bench


if __name__ == "__main__":
    main()
