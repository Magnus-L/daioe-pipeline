"""Stage 2b: the capability transform's declared properties, as tests.

The gate checks these on live data every run; these tests check the machinery itself on
constructed cases, so a regression is caught without needing the full data tree.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from daioe import stage2b_capability as cap


def test_theta_is_zero_at_parity_for_every_scale_family():
    """theta is defined as the log-distance from the human anchor, so parity must read 0."""
    cases = [
        ("Percentage correct", 80.0),
        ("Percentage error", 12.0),
        ("FID", 3.5),
        ("Perplexity", 20.0),
        ("Model Entropy", 1.2),
        ("Score", 40.0),
        ("ELO rating", 1500.0),
        ("BLEU score", 35.0),
    ]
    for scale, anchor in cases:
        th = cap._theta(scale, np.array([anchor]), anchor)
        assert abs(float(th[0])) < 1e-9, f"{scale} does not read 0 at parity"


def test_theta_sign_follows_direction_not_magnitude():
    """The defect this transform was built to fix: direction-blind comparison.

    Higher-is-better and lower-is-better families must both give theta > 0 for a machine
    that beats the human, even though one does it by a larger number and one by a smaller.
    """
    assert cap._theta("Percentage correct", np.array([90.0]), 80.0)[0] > 0
    assert cap._theta("Percentage correct", np.array([70.0]), 80.0)[0] < 0
    # lower is better: a smaller error beats the human
    assert cap._theta("Percentage error", np.array([6.0]), 12.0)[0] > 0
    assert cap._theta("Percentage error", np.array([18.0]), 12.0)[0] < 0
    assert cap._theta("FID", np.array([1.0]), 3.5)[0] > 0
    assert cap._theta("Perplexity", np.array([10.0]), 20.0)[0] > 0
    assert cap._theta("Model Entropy", np.array([0.8]), 1.2)[0] > 0


def test_signed_log_handles_negative_scores():
    """Atari scores go negative (Pong runs -21 to +21), so the Score family must not blow up."""
    out = cap._signed_log(np.array([-21.0, 0.0, 21.0]))
    assert np.isfinite(out).all()
    assert out[0] < 0 < out[2]
    assert out[1] == 0.0


def test_unknown_scale_raises_rather_than_returning_nan():
    """A silent NaN would remove a metric from the basket with no error path."""
    with pytest.raises(ValueError, match="unhandled scale"):
        cap._theta("Bananas", np.array([1.0]), 1.0)


def test_information_weight_vanishes_at_a_degenerate_ceiling():
    """The measured reason TheAgentCompany cannot corroborate METR.

    An undiscounted 100.0 ceiling puts a percentage series ~15 log-odds below its anchor, so
    its Fisher weight is ~0 and it contributes nothing however much it moves. This is the
    property that turned a suspicion into a number (weight share 2.5e-06), so it is worth a
    regression test.
    """
    th_ceiling = cap._theta("Percentage correct", np.array([33.1]), 100.0)[0]
    th_real = cap._theta("Score", np.array([352.2]), 960.0)[0]
    w = lambda t: (1 / (1 + np.exp(-t))) * (1 - 1 / (1 + np.exp(-t)))
    assert th_ceiling < -14
    assert w(th_ceiling) < 1e-6
    assert w(th_real) > 0.1
    assert w(th_ceiling) / w(th_real) < 1e-5


def test_gate_flags_negative_progress():
    """Composition-neutrality is the reason for weighting changes rather than levels."""
    app = pd.DataFrame({"delta_p": [0.4, 0.0, -0.3, np.nan]})
    g = cap._gate_no_negative_progress(app)
    assert not g.passed
    assert "1 of 3" in g.detail


def test_gate_passes_when_no_progress_is_negative():
    app = pd.DataFrame({"delta_p": [0.4, 0.0, 0.3]})
    assert cap._gate_no_negative_progress(app).passed


def test_gate_flags_a_falling_frontier():
    """theta is a running max by construction; a fall means the direction logic is wrong."""
    bench = pd.DataFrame(
        {"d_theta": [0.2, -0.5, np.nan], "scale": ["Percentage error"] * 3}
    )
    g = cap._gate_monotone_frontier(bench)
    assert not g.passed
    assert "Percentage error" in g.detail
