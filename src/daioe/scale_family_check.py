"""Do our metric transforms handle different TYPES of metric, and how would we know?

Written 18 Aug 2026, after the METR admission raised the question in a sharp form and the
answer turned out to be reassuring. Magnus's framing, and it is the right one: changing how
DAIOE computes is a large and mostly unwelcome step, whereas making the handling of metric
types explicit and checked is a small one that pays off on every future admission.

## The property this module exists to make visible

The eight scale families are NOT commensurable, and never have been. One unit of progress
means a different thing in each:

    Score               +0.372 (the family median) = raw value x1.45
    Percentage correct  +0.141 (the family median) = remaining error x0.868, e.g. 80% -> 82.6%
    Percentage error    +0.116 (the family median) = error x0.891

A ratio-scale family with no ceiling therefore produces systematically larger increments
than a family referenced to one. Measured over 911 metric-year increments, 2010-2025:

    family              n     median    p90      max
    Score              470     0.372    1.453   11.027
    FID                 29     0.362    0.955    1.171
    Percentage correct 172     0.141    0.750    3.091
    Percentage error    97     0.116    0.459    1.137
    Model Entropy       23     0.062    0.179    0.839
    Perplexity          24     0.055    0.648    0.753
    BLEU score          49     0.043    0.189    0.337
    ELO rating          47     0.012    0.221    0.551

Score runs about 2.6 times Percentage correct at the median. That is a property of the
frozen construction, present since 2010, not something a new series introduced.

## Why that is a reason NOT to change the construction

METR's agentic increment of 2.2051 reads as an order of magnitude above the other 2025
applications, which is what prompted the question. Placed against its own family it is
ordinary: the **96.6th percentile of the 469 prior Score-family increments**, below that
family's 99th percentile of 3.285, and well below the largest increment the published index
has ever carried, Atari 2600 Pitfall! at 11.027 in 2019. Four of the five largest increments
in the entire history are Atari games inside the frozen, published window.

So the index has absorbed increments of this size and larger for a decade. What made 2025
look different is not METR but coverage: the nine original applications have largely stopped
being measured (five of nine have no living source), so a normal fast series has nothing to
sit beside. That is issue 4, not a transform defect.

## What this module does

It turns the paragraph above into a check that runs, so the next series is assessed against
its own family rather than against a general impression:

    report()          the family table above, recomputed from whatever data is in hand
    check_series()    where one series' increments sit inside its own family's distribution

A series above its family's 99th percentile is FLAGGED. That is the signal worth having: not
"this number is big" but "this series does not behave like its type", which is what a wrong
scale declaration, a units error or a mis-set anchor actually looks like.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# quantiles reported for every family
QS = (0.25, 0.5, 0.75, 0.9, 0.95, 0.99)
# a series above its family's 99th percentile is flagged for a human look
FLAG_Q = 0.99


def _increments(frontiers: pd.DataFrame, formated: pd.DataFrame) -> pd.DataFrame:
    """Non-zero metric-year increments, tagged with each metric's declared scale family."""
    scale = formated.drop_duplicates("metrics_name").set_index("metrics_name")["scale"]
    d = frontiers.copy()
    d["scale"] = d["metrics_name"].map(scale)
    return d[d["deltafinal"].notna() & (d["deltafinal"] != 0) & d["scale"].notna()].copy()


def report(frontiers: pd.DataFrame, formated: pd.DataFrame) -> pd.DataFrame:
    """Increment distribution per scale family: the table in this module's docstring."""
    d = _increments(frontiers, formated)
    t = d.groupby("scale")["deltafinal"].describe(percentiles=list(QS))
    keep = ["count", "50%", "90%", "99%", "max"]
    return t[keep].rename(columns={"50%": "median", "90%": "p90", "99%": "p99"}) \
                  .sort_values("median", ascending=False)


@dataclass
class FamilyVerdict:
    metrics_name: str
    scale: str
    n_own: int
    n_family: int
    max_increment: float
    percentile: float
    family_p99: float
    flagged: bool

    def summary(self) -> str:
        head = "FLAG" if self.flagged else "OK"
        return (f"[{head}] {self.metrics_name!r} ({self.scale}): largest increment "
                f"{self.max_increment:.4f}, {self.percentile:.1f}th percentile of "
                f"{self.n_family} prior {self.scale} increments "
                f"(family p99 = {self.family_p99:.3f})")


def check_series(frontiers: pd.DataFrame, formated: pd.DataFrame,
                 metrics_name: str) -> FamilyVerdict:
    """Where does one series sit inside its own family's increment distribution?

    The comparison excludes the series itself, so a series cannot normalise its own
    reference. With no prior family members the verdict is unflagged and n_family is 0: an
    unprecedented family is a fact to report, not a failure to assert.
    """
    d = _increments(frontiers, formated)
    own = d[d["metrics_name"] == metrics_name]
    if own.empty:
        raise ValueError(f"{metrics_name!r} has no non-zero increments to check")
    scale = own["scale"].iloc[0]
    others = d[(d["scale"] == scale) & (d["metrics_name"] != metrics_name)]["deltafinal"]
    worst = float(own["deltafinal"].max())
    if others.empty:
        return FamilyVerdict(metrics_name, scale, len(own), 0, worst, float("nan"),
                             float("nan"), False)
    pct = float((others < worst).mean() * 100)
    p99 = float(others.quantile(FLAG_Q))
    return FamilyVerdict(metrics_name, scale, len(own), len(others), worst, pct, p99,
                         worst > p99)
