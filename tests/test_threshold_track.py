"""Tests for the level-threshold parallel track.

Two of these matter more than the rest.

`test_threshold_tail_reproduces_build_panel` pins the reimplementation: fed a plain relatedness score
instead of a threshold, `threshold_panel.build` must reproduce `build_2024_variants.build_panel`
exactly. Without that, any difference the threshold appears to make could just as easily be a bug in
the arithmetic downstream of it.

`test_required_levels_are_raw_not_normalised` guards the mistake this track exists to avoid. The
checkpoint carries `level_scaled` (0 to 0.911); the anchors refer to O*NET's 0-7 scale. Comparing an
attained level against a normalised share would silently make every occupation look unprotected.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "mapping"

pytestmark = pytest.mark.skipif(
    not (ROOT / "data" / "raw" / "Work_Activities_Onet_Feb2018_22_2.xlsx").exists(),
    reason="O*NET work activities not present",
)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, MAP / "code" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def elements():
    return pd.read_csv(MAP / "raw_data" / "abilities_v2.csv")


# --------------------------- weights and levels ---------------------------

def test_required_levels_are_raw_not_normalised(elements):
    """Anchors refer to O*NET's 0-7 level scale, not the checkpoint's normalised share."""
    tw = _load("threshold_weights")
    for block in ("ability", "activity"):
        req, _ = tw.block_matrices(block, elements)
        assert req.values.max() > 3.0, f"{block}: max required level {req.values.max():.2f} looks normalised"
        assert req.values.max() <= 7.0


def test_social_block_weight_varies_across_occupations(elements):
    """The bug that put glass blowers top of the social ranking.

    Normalising a block within itself makes every occupation's block sum to 1, so social intensity
    disappears and only composition survives. Each block must be a share of its own full O*NET
    domain instead.
    """
    tw = _load("threshold_weights")
    for block in ("social_skill", "activity"):
        _, w = tw.block_matrices(block, elements)
        block_sum = w.sum(axis=1)
        assert block_sum.std() > 0.01, f"{block}: block weight is constant across occupations"
        assert block_sum.max() < 0.95


def test_ability_backbone_sums_to_one(elements):
    """The 52 abilities are the backbone and share their own domain, as element_impact does."""
    tw = _load("threshold_weights")
    _, w = tw.block_matrices("ability", elements)
    assert np.allclose(w.sum(axis=1), 1.0)


# --------------------------- the construction ---------------------------

def test_threshold_tail_reproduces_build_panel(elements):
    """Fed relatedness instead of a threshold, the two constructions must agree exactly."""
    bv, tp = _load("build_2024_variants"), _load("threshold_panel")
    apps = pd.read_csv(MAP / "raw_data" / "applications_v2.csv")
    progress = bv.load_progress()
    w52, _ = bv.load_weights(None)
    M = bv.matrix_claude(apps, MAP / "output" / "mapping_matrix_claude_v2026.csv")

    cols = [c for c in M.columns if c in w52.columns]
    M2, W2 = M[cols], w52[cols]
    ref = bv.build_panel(M2, W2, progress, None, 10.0)

    A = pd.DataFrame(W2.values @ M2.loc[M.index][cols].values.T,
                     index=W2.index, columns=list(M.index))
    alt = tp.build(A, progress, {n: n for n in M.index}, 10.0)

    j = ref.merge(alt, on=["occ_code_onet", "year"], suffixes=("_ref", "_alt"))
    assert len(j) > 10_000
    assert np.allclose(j.exp_change_ref, j.exp_change_alt)
    assert np.allclose(j.exp_cumul_ref, j.exp_cumul_alt)


def test_reach_is_bounded_and_finite(elements):
    """A(o,i) is a weighted average of logistics, so it cannot exceed the block weight total."""
    tw, tp = _load("threshold_weights"), _load("threshold_panel")
    blocks = ["activity"]
    req, w = tw.load(blocks, elements)
    att = tp.load_attained(blocks, elements)
    A = tp.reach(att, req, w, 1.0)
    assert np.isfinite(A.values).all()
    assert (A.values >= 0).all()
    assert A.values.max() <= w.sum(axis=1).max() + 1e-9


def test_higher_required_level_means_less_reach(elements):
    """The whole point: an occupation needing more of an element is reached less, all else equal."""
    tw, tp = _load("threshold_weights"), _load("threshold_panel")
    req, w = tw.load(["activity"], elements)
    att = tp.load_attained(["activity"], elements)

    flat = pd.DataFrame(np.ones_like(w.values) / w.shape[1], index=w.index, columns=w.columns)
    A = tp.reach(att, req, flat, 1.0)
    demand = req.mean(axis=1)
    lo, hi = demand.nsmallest(50).index, demand.nlargest(50).index
    assert A.loc[lo].mean().mean() > A.loc[hi].mean().mean()


# --------------------------- separation ---------------------------

def test_track_does_not_modify_the_production_pipeline(elements, tmp_path):
    """Behavioural, not a grep.

    An earlier version of this test searched the source text for `src/daioe` and failed on the
    docstrings that promise the track avoids it. What matters is whether anything is written, so
    snapshot every file under the production directories, run the construction, and compare.
    """
    tw, tp = _load("threshold_weights"), _load("threshold_panel")
    watched = [ROOT / "src" / "daioe", ROOT / "data" / "out"]

    def snapshot():
        out = {}
        for d in watched:
            for p in d.rglob("*"):
                if p.is_file():
                    st = p.stat()
                    out[str(p)] = (st.st_mtime_ns, st.st_size)
        return out

    before = snapshot()
    assert before, "nothing to watch; the production directories are missing"

    req, w = tw.load(["activity"], elements)
    att = tp.load_attained(["activity"], elements)
    A = tp.reach(att, req, w, 1.0)
    bv = _load("build_2024_variants")
    tp.build(A, bv.load_progress(),
             dict(zip(pd.read_csv(MAP / "raw_data" / "applications_v2.csv").ai_app_id,
                      pd.read_csv(MAP / "raw_data" / "applications_v2.csv").frs_row.str.strip().str.lower())))

    after = snapshot()
    assert after == before, (
        "the threshold track modified production files: "
        f"{sorted(set(after) ^ set(before)) or [k for k in before if after.get(k) != before[k]]}"
    )
