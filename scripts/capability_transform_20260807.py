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

# The arithmetic now lives in the package (src/daioe/stage2b_capability.py) so the pipeline
# can run it behind a validation gate; this script stays as the exhibit that produced the
# tables in DESIGN-capability-transform_2026-08-07.md, and imports rather than duplicating.
# Moved 13 Aug 2026 when the transform became a prerequisite for the METR agentic switch.
from daioe.stage2b_capability import (  # noqa: E402
    ANCHOR_FIX,
    _signed_log,
    _theta,
    build_capability,
    load_sourced_anchors,
)

LOWER_IS_BETTER = {"Percentage error", "FID", "Perplexity", "Model Entropy"}
ANCHOR_TABLE = ROOT / "data/derived/human_anchors_v1.csv"


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
