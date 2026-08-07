"""Tests for the v2 mapping pipeline: anchor balance, held-out accounting, and FRS alignment.

The load-bearing test here is `test_published_matrix_reproduces_appendix_j`. The validator's whole
value is that it settles design questions by agreement with the expert matrix, and that is worth
nothing if the alignment silently drifts. Pinning it to the published figure means any future change
to the ability map, the application map or the FRS reader fails loudly rather than quietly moving
the bar the new runs are judged against.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
MAPPING = ROOT / "mapping"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, MAPPING / "code" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


pytestmark = pytest.mark.skipif(
    not (MAPPING / "raw_data" / "mapping_matrix.xlsx").exists(),
    reason="FRS matrix not present",
)


@pytest.fixture(scope="module")
def anchors():
    return pd.read_csv(MAPPING / "raw_data" / "anchors_v2.csv")


@pytest.fixture(scope="module")
def apps():
    return pd.read_csv(MAPPING / "raw_data" / "applications_v2.csv")


# --------------------------- anchors ---------------------------

def test_every_application_gets_the_same_amount_of_calibration(anchors, apps):
    """The published defect: app 1 had 17 high / 17 low, app 4 had 1 / 0, apps 10-12 had none.

    Unequal calibration means the applications were not scored by one instrument, which is fatal for
    a matrix whose whole job is to compare across applications.
    """
    counts = anchors.groupby(["ai_app_id", "label"]).size().unstack(fill_value=0)
    assert set(counts.index) == set(apps.ai_app_id), "an application has no anchors at all"
    assert counts.nunique().eq(1).all(), f"anchor counts differ across applications:\n{counts}"


def test_low_anchors_span_multiple_onet_domains(anchors):
    """FRS rows carry long contiguous runs of 0.00, and O*NET orders abilities by domain.

    Breaking ties by adjacent id therefore hands the model five zeros from one domain, so it learns
    what 'no support' looks like in the sensory corner and nowhere else.
    """
    def domain(i):
        return "cognitive" if i <= 21 else "psychomotor" if i <= 31 else "physical" if i <= 40 else "sensory"

    low = anchors[anchors.label == "low"]
    per_app = low.groupby("ai_app_id").ability_id.apply(lambda s: s.map(domain).nunique())
    assert (per_app >= 2).all(), f"low anchors confined to one domain for apps {list(per_app[per_app < 2].index)}"


def test_anchors_never_drawn_from_the_social_skills(anchors):
    """Abilities 53-58 have no FRS counterpart, so no anchor can honestly claim an FRS score."""
    assert anchors.ability_id.max() <= 52


def test_new_subdomains_declare_their_frs_provenance(apps):
    new = apps[apps.ai_app_id.isin([10, 11, 12])]
    assert len(new) == 3
    assert new.frs_row.notna().all() and (new.frs_row.str.len() > 0).all()
    # Only the agentic mapping is approximate; if that ever silently becomes 'exact' the
    # judgement recorded in the note has been lost.
    assert new.set_index("ai_app_id").loc[10, "frs_match"] == "approximate"


# --------------------------- validation ---------------------------

def test_published_matrix_reproduces_appendix_j():
    """Pin the alignment to Online Appendix J: Pearson 0.7762, MAE 0.1258, n=468."""
    v = _load("validate_mapping_v2")
    apps = pd.read_csv(MAPPING / "raw_data" / "applications_v2.csv")
    abilities = pd.read_csv(MAPPING / "raw_data" / "abilities.csv")

    mat = pd.read_csv(MAPPING / "output" / "mapping_matrix_9x58_v2018.csv", index_col=0)
    mat.columns = [int(c) for c in mat.columns]
    ours = mat.stack().reset_index()
    ours.columns = ["ai_app_id", "ability_id", "ours"]
    ours = ours[ours.ability_id <= 52]

    comp = ours.merge(v.frs_long(apps, abilities), on=["ai_app_id", "ability_id"]).dropna()
    s = v.stats(comp)
    assert s["n"] == 468
    assert s["pearson"] == pytest.approx(0.7762, abs=5e-4)
    assert s["mae"] == pytest.approx(0.1258, abs=5e-4)


def test_excluding_anchored_cells_lowers_agreement():
    """The anchored cells had their FRS value printed in the prompt that produced them.

    Agreement must therefore fall when they are removed. If it ever does not, the held-out set is
    not being applied and the reported figure is the inflated one under an honest name.
    """
    v = _load("validate_mapping_v2")
    apps = pd.read_csv(MAPPING / "raw_data" / "applications_v2.csv")
    abilities = pd.read_csv(MAPPING / "raw_data" / "abilities.csv")

    mat = pd.read_csv(MAPPING / "output" / "mapping_matrix_9x58_v2018.csv", index_col=0)
    mat.columns = [int(c) for c in mat.columns]
    ours = mat.stack().reset_index()
    ours.columns = ["ai_app_id", "ability_id", "ours"]
    comp = ours[ours.ability_id <= 52].merge(
        v.frs_long(apps, abilities), on=["ai_app_id", "ability_id"]).dropna()

    excl = set(map(tuple, v.legacy_anchor_cells(MAPPING / "raw_data" / "anchors.csv").values))
    held = comp[[(a, b) not in excl for a, b in zip(comp.ai_app_id, comp.ability_id)]]

    assert len(held) < len(comp), "no anchored cells were excluded"
    assert v.stats(held)["pearson"] < v.stats(comp)["pearson"]


# --------------------------- request construction ---------------------------

def test_sweep_sample_avoids_anchored_cells_and_is_stratified():
    """A sweep compares settings on held-out agreement, so an anchored cell cannot discriminate:
    every setting is handed the answer."""
    e = _load("estimate_mapping_claude")
    apps = pd.read_csv(MAPPING / "raw_data" / "applications_v2.csv")
    abilities = pd.read_csv(MAPPING / "raw_data" / "abilities.csv")

    picked = e.sample_cells(apps, abilities, per_app=5, seed=1)
    anchored = set(map(tuple, pd.read_csv(MAPPING / "mod_data" / "anchor_cells_v2.csv").astype(int).values))

    assert not (picked & anchored)
    assert all(b <= 52 for _, b in picked)
    per_app = pd.Series([a for a, _ in picked]).value_counts()
    assert set(per_app.index) == set(apps.ai_app_id) and per_app.nunique() == 1


def test_replicates_rotate_the_anchor_window(anchors, apps):
    """Replicate variation has to come from somewhere real: Opus 5 rejects `temperature` with a 400.

    It comes from showing each replicate a different window of the same eight FRS exemplars, so the
    spread across replicates measures sensitivity to the choice of exemplar rather than decoding
    noise. If the windows ever coincide, the dispersion column becomes decorative.
    """
    e = _load("estimate_mapping_claude")
    app = apps[apps.ai_app_id == 1].iloc[0]
    blocks = [e.build_system(app, anchors, r)[1]["text"] for r in range(3)]
    assert len(set(blocks)) == 3, "replicates show identical calibration blocks"


def test_temperature_is_never_sent(anchors, apps):
    """Opus 5 returns 400 for temperature, top_p and top_k. The original set temperature=0.2."""
    e = _load("estimate_mapping_claude")
    abilities = pd.read_csv(MAPPING / "raw_data" / "abilities.csv")
    reqs = e.build_requests(apps, abilities, anchors, replicates=1, effort="high",
                            max_tokens=4000, limit=5)
    for r in reqs:
        assert not ({"temperature", "top_p", "top_k"} & set(r["params"]))
