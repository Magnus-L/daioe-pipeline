"""
threshold_panel.py — exposure from attained-versus-required levels rather than from relatedness.

Parallel track. Writes only to `mapping/reports/threshold_track/`; touches nothing the published
index or the 2024 vintage work depends on.

The construction
----------------
The published measure asks whether an application supports an ability. This asks how far up the
ability's own anchored scale the application gets, and compares that with what the occupation needs:

    exp_change(o,t) = Σ_j w(o,j) · Σ_i g(attained(i,j) − required(o,j)) · p(i,t)
                    = Σ_i p(i,t) · A(o,i),   A(o,i) = Σ_j w(o,j) · g(attained(i,j) − required(o,j))

The occupation dependence collapses into `A`, a 966 x 13 matrix computed once, so the matrix never
has to be materialised as application x element x occupation. Everything after Eq3 — squaring, the
scale-up, the cumulation — is unchanged from `build_2024_variants.build_panel`, and
`tests/test_threshold_track.py` pins that by checking the two agree exactly when the threshold is
replaced by a plain relatedness score.

`g` is a logistic in the level gap. `steepness` controls how sharply an occupation is protected once
its requirement exceeds what AI attains; 1.0 means a one-level gap leaves about 27 per cent reach.
It is a free parameter and the validation sweeps it.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

MAP = Path(__file__).resolve().parents[1]
ROOT = MAP.parent
REPORTS = MAP / "reports" / "threshold_track"
REPORTS.mkdir(parents=True, exist_ok=True)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, MAP / "code" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


bv = _load("build_2024_variants")
tw = _load("threshold_weights")


def load_attained(blocks: list[str], elements: pd.DataFrame) -> pd.DataFrame:
    """Attained level per (application, element), assembled from the level-scoring runs."""
    frames = []
    for tag in ("activity", "ability_social_skill"):
        p = MAP / "mod_data" / f"levels_cells_{tag}.csv"
        if p.exists():
            frames.append(pd.read_csv(p))
    if not frames:
        raise SystemExit("no level-scoring output found; run score_activity_levels.py first")
    lv = pd.concat(frames, ignore_index=True)

    keep = elements[elements.block.isin(blocks)]
    lv = lv[lv.ability_id.isin(keep.ability_id)]
    att = lv.pivot(index="ai_app_id", columns="ability_id", values="level")
    return att.rename(columns=dict(zip(elements.ability_id, elements.element_id)))


def reach(attained: pd.DataFrame, required: pd.DataFrame, weight: pd.DataFrame,
          steepness: float) -> pd.DataFrame:
    """A(o, i): the share of occupation o's work that application i reaches.

    Computed application by application because the logistic is over an occupation x element grid;
    13 passes over a 966 x 75 array, so the loop costs nothing and keeps the shapes readable.
    """
    cols = [c for c in attained.columns if c in required.columns]
    if not cols:
        raise ValueError("no elements shared between the attained levels and the O*NET requirements")
    req, wgt = required[cols].values, weight[cols].values
    out = {}
    for app_id in attained.index:
        gap = attained.loc[app_id, cols].values[None, :] - req
        out[app_id] = (wgt * (1.0 / (1.0 + np.exp(-steepness * gap)))).sum(axis=1)
    return pd.DataFrame(out, index=required.index)


def build(A: pd.DataFrame, progress: pd.DataFrame, app_names: dict[int, str],
          scale_up: float = 10.0) -> pd.DataFrame:
    """exp_change = A @ P, then the unchanged square / scale / cumulate tail."""
    rows = []
    for year, g in progress.groupby("year"):
        p = g.set_index("application")["progress"]
        cols = [i for i in A.columns if app_names.get(i) in p.index]
        if not cols:
            continue
        vals = A[cols].values @ p.loc[[app_names[i] for i in cols]].values
        rows.append(pd.DataFrame({"occ_code_onet": A.index, "year": year, "exp_change": vals}))

    panel = pd.concat(rows, ignore_index=True)
    panel["exp_change"] = panel.exp_change ** 2 * scale_up
    panel = panel.sort_values(["occ_code_onet", "year"])
    panel["exp_cumul"] = panel.groupby("occ_code_onet").exp_change.cumsum()
    return panel.reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", default="ability,activity",
                    help="element blocks to include: ability, social_skill, activity")
    ap.add_argument("--steepness", type=float, default=1.0)
    ap.add_argument("--scale-up", type=float, default=10.0)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    blocks = [b.strip() for b in args.blocks.split(",")]
    tag = args.tag or "_".join(blocks)

    elements = pd.read_csv(MAP / "raw_data" / "abilities_v2.csv")
    apps = pd.read_csv(MAP / "raw_data" / "applications_v2.csv")
    app_names = dict(zip(apps.ai_app_id, apps.frs_row.str.strip().str.lower()))

    required, weight = tw.load(blocks, elements)
    attained = load_attained(blocks, elements)
    missing = [b for b in blocks
               if not set(elements[elements.block == b].element_id) & set(attained.columns)]
    if missing:
        raise SystemExit(f"no attained levels scored yet for block(s) {missing}")

    A = reach(attained, required, weight, args.steepness)
    A.to_csv(REPORTS / f"reach_A_{tag}.csv")

    panel = build(A, bv.load_progress(), app_names, args.scale_up)
    panel.to_csv(REPORTS / f"panel_{tag}.csv", index=False)

    final = panel[panel.year == panel.year.max()].set_index("occ_code_onet").exp_cumul
    print(f"blocks {blocks}  steepness {args.steepness}")
    print(f"  A: {A.shape[0]} occupations x {A.shape[1]} applications, "
          f"reach {A.values.min():.3f}-{A.values.max():.3f}")
    print(f"  panel: {panel.year.min():.0f}-{panel.year.max():.0f}, {len(final)} occupations")
    print(f"  wrote {REPORTS / f'panel_{tag}.csv'}")


if __name__ == "__main__":
    main()
