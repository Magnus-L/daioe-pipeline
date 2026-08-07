"""
compute_occupation_exposure.py — From mapping M and O*NET weights W to occupation exposure

Purpose (non-programmer summary):
- Combine our application–ability mapping (M) with occupation–ability weights (W)
  to obtain exposure by occupation.
- Provide two summary measures:
    A) Exposure without social-skill down-weighting.
    B) A DAIOE-style variant that reduces exposure as the share of social-skill content rises.
- Also compute the *social share* used by (B).

Inputs:
- M: pandas.DataFrame with rows = applications (9), columns = ability/skill IDs (1..58).
     Index should be application IDs (ai_app_id).
- W: pandas.DataFrame with rows = occupations, columns = ability/skill IDs (1..58).
     Index should be occupation codes (O*NET-SOC 2010).

Outputs (returns):
- (E_A, E_B, s_share): three pandas.Series indexed by occupation.
    E_A: exposure without down-weighting (sum over applications).
    E_B: DAIOE-style down-weighted exposure (monotone in social share).
    s_share: share of exposure attributed to social skills (IDs 53..58).

Notes:
- The precise DAIOE down-weighting in published work can be swapped in here if needed.
- We use a simple, transparent rule: E_B = E_A / (1 + delta * s_share)**gamma.
- Parameters gamma and delta can be tuned in the master pipeline.
"""

from __future__ import annotations
import numpy as np
import pandas as pd

SOCIAL_IDS = list(range(53, 59))  # 53..58

def compute_exposure(M: pd.DataFrame, W: pd.DataFrame, gamma: float = 1.0, delta: float = 2.0):
    """
    Parameters
    ----------
    M : DataFrame  (apps × abilities), abilities named with integer IDs 1..58
    W : DataFrame  (occ × abilities), abilities named with integer IDs 1..58
    gamma : float  exponent for the down-weighting
    delta : float  slope for the down-weighting

    Returns
    -------
    (E_A, E_B, s_share) : tuple of Series (indexed by occupations)
    """
    # Ensure column alignment (intersect abilities present in both M and W)
    abil = [c for c in W.columns if c in M.columns]
    M2 = M[abil].copy()
    W2 = W[abil].copy()

    # Occupation-by-application exposure matrix: W (occ×abil) · M^T (abil×apps)
    E_matrix = W2.values.dot(M2.T.values)  # shape: occ × apps
    occ_index = W2.index
    app_index = M2.index

    # Aggregate exposure across the nine applications
    E_A = pd.Series(E_matrix.sum(axis=1), index=occ_index, name="exposure_A")

    # Social-only exposure (sum over apps of exposure using only social abilities 53..58)
    soc_cols = [c for c in abil if c in SOCIAL_IDS]
    if soc_cols:
        E_soc = W2[soc_cols].values.dot(M2[soc_cols].T.values).sum(axis=1)
    else:
        E_soc = np.zeros(len(occ_index))
    # Share of social exposure (guard against divide-by-zero)
    denom = np.where(E_A.values>0, E_A.values, np.nan)
    s_share = pd.Series(E_soc / denom, index=occ_index).fillna(0.0).clip(0.0, 1.0)
    s_share.name = "social_share"

    # DAIOE-style down-weighting: larger social share => smaller exposure
    E_B = E_A / (1.0 + delta * s_share.values)**gamma
    E_B = pd.Series(E_B, index=occ_index, name="exposure_B")

    return E_A, E_B, s_share
