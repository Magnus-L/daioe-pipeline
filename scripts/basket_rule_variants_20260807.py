#!/usr/bin/env python3
"""Quantify the basket rule: mean over survivors vs fixed basket with carried-forward zeros.

Written 7 August 2026 to settle the question left open by
``notes/FINDING-basket-thinning-2026-08-06.md``, which established that the published
index thins to a single benchmark in four of nine applications by 2023 but deliberately
stopped short of costing the alternative.

WHAT THE PUBLISHED CONSTRUCTION ALREADY DOES. ``build_metrics_frontiers`` restricts each
metric to its observed span [min_year, max_year] and sets ``deltafinal = 0`` in span years
with no SOTA jump (do-file line 428). So zeros are ALREADY carried inside a metric's span.
The only thing at issue is the right tail: what happens after a metric's last observation.

THE VARIANTS. All share the same numerator, sum(deltafinal); they differ only in the
denominator, so each is a per-(application, year) rescaling of the published progress score:

  P    published    / count of metrics observed that year          [status quo]
  CF   carry-fwd    / count of metrics born by that year           [once in, always in]
  FIX  fully fixed  / count of metrics ever in the application     [bound; penalises early years]
  MIN3 min-count    published mean, application drops when count < 3

Part D pushes CF through Stage 4 to the occupation level, because the decisive question for
the flagship paper is not what happens to the levels (they fall a lot) but what happens to
the cross-occupation ordering the regressions identify from (it barely moves).

Run:  .venv/bin/python scripts/basket_rule_variants_20260807.py
Reads data/out only; writes nothing into data/out. Safe to run against the frozen state.
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

from daioe import config as cfgmod, stage4_index as s4  # noqa: E402

YEARS = np.arange(2010, 2024)


def build_variants(frontiers: pd.DataFrame) -> pd.DataFrame:
    """Application-year progress under each denominator rule."""
    span = (
        frontiers.groupby(["metrics_name", "parent_name"])["year"]
        .agg(first_year="min", last_year="max")
        .reset_index()
    )
    rows = []
    for app in sorted(frontiers["parent_name"].unique()):
        sub = frontiers[frontiers["parent_name"] == app]
        sp = span[span["parent_name"] == app]
        for y in YEARS:
            obs = sub[sub["year"] == y]
            s = obs["deltafinal"].sum()
            n_obs = int(obs["deltafinal"].notna().sum())
            n_born = int((sp["first_year"] <= y).sum())
            if n_obs == 0 and n_born == 0:
                continue
            rows.append(
                dict(
                    application=app, year=y, n_obs=n_obs, n_born=n_born, n_ever=len(sp),
                    sum_delta=s,
                    P=s / n_obs if n_obs else np.nan,
                    CF=s / n_born if n_born else np.nan,
                    FIX=s / len(sp),
                )
            )
    v = pd.DataFrame(rows)
    v["MIN3"] = np.where(v["n_obs"] >= 3, v["P"], 0.0)
    return v


def cf_slopes(frontiers: pd.DataFrame) -> pd.DataFrame:
    """The carry-forward mean per (parent_name, year), for patching into Stage 2 output."""
    span = frontiers.groupby(["metrics_name", "parent_name"])["year"].min().reset_index(
        name="first_year"
    )
    agg = (
        frontiers.groupby(["parent_name", "year"])
        .agg(sum_delta=("deltafinal", "sum"))
        .reset_index()
    )
    born = []
    for _, r in agg.iterrows():
        sp = span[span["parent_name"] == r["parent_name"]]
        born.append(int((sp["first_year"] <= r["year"]).sum()))
    agg["n_born"] = born
    agg["mean_cf"] = agg["sum_delta"] / agg["n_born"]
    return agg[["parent_name", "year", "mean_cf"]]


def occupation_comparison(cfg, patch: pd.DataFrame) -> None:
    """Run Stage 4 twice, published slopes vs carry-forward slopes, and compare."""
    tmp = Path(tempfile.mkdtemp(prefix="daioe_cf_"))
    for p in (ROOT / "data/out").glob("*.parquet"):
        shutil.copy(p, tmp / p.name)
    for cat in cfg.app_categories:
        f = tmp / f"slopes_slimmed_{cat}.parquet"
        s = pd.read_parquet(f).merge(patch, on=["parent_name", "year"], how="left")
        # the robotics dummy row carries mean=1.0 and has no frontier data; leave it.
        s["mean"] = (
            np.where(s["mean_cf"].notna(), s["mean_cf"], s["mean"])
            .astype(np.float32)
            .astype(float)
        )
        s.drop(columns="mean_cf").to_parquet(f, index=False)

    raw = dict(cfg.raw)
    raw["paths"] = dict(cfg.raw["paths"])
    raw["paths"]["out"] = str(tmp)
    cfg_cf = cfgmod.Config(raw=raw, root=cfg.root)

    pub = s4.build(cfg)["preliminary"]
    cf = s4.build(cfg_cf)["preliminary"]

    for app in ("allapps", "genai"):
        col = f"exp_cumul_{app}"
        for yr in (2016.0, 2020.0, 2023.0):
            a = pub[pub["year"] == yr][["occ_code_onet", col]].rename(columns={col: "pub"})
            b = cf[cf["year"] == yr][["occ_code_onet", col]].rename(columns={col: "cf"})
            j = a.merge(b, on="occ_code_onet", validate="1:1")
            sp = stats.spearmanr(j["pub"], j["cf"]).statistic
            pp = j["pub"].rank(pct=True) * 100
            pc = j["cf"].rank(pct=True) * 100
            shift = (pc - pp).abs()
            top = ((pp > 90) & (pc > 90)).sum() / (pp > 90).sum() * 100
            print(
                f"{app:8s} {int(yr)}  cf/pub level={j['cf'].mean()/j['pub'].mean():5.3f}  "
                f"spearman={sp:.4f}  mean|pctl shift|={shift.mean():5.2f}pts  "
                f"max={shift.max():5.2f}  top-decile retained={top:5.1f}%"
            )
    print()
    for app in ("allapps", "genai"):
        col = f"exp_change_{app}"
        for yr in (2021.0, 2022.0, 2023.0):
            a = pub[pub["year"] == yr][["occ_code_onet", col]].rename(columns={col: "pub"})
            b = cf[cf["year"] == yr][["occ_code_onet", col]].rename(columns={col: "cf"})
            j = a.merge(b, on="occ_code_onet", validate="1:1")
            print(
                f"increment {app:8s} {int(yr)}  cf/pub={j['cf'].mean()/j['pub'].mean():5.3f}  "
                f"spearman={stats.spearmanr(j['pub'], j['cf']).statistic:.4f}"
            )
    shutil.rmtree(tmp)


def main() -> None:
    pd.set_option("display.width", 200)
    cfg = cfgmod.load_config(ROOT / "config.yaml")
    f = pd.read_parquet(ROOT / "data/out/metrics_frontiers.parquet")
    v = build_variants(f)

    print("=" * 92)
    print("A. Application-year progress under each denominator rule")
    print("=" * 92)
    for app in sorted(v["application"].unique()):
        s = v[v["application"] == app]
        print(f"\n--- {app}  (metrics ever: {s['n_ever'].iloc[0]}) ---")
        print(
            s[["year", "n_obs", "n_born", "P", "CF", "FIX"]].to_string(
                index=False, float_format=lambda x: f"{x:8.4f}"
            )
        )

    print("\n" + "=" * 92)
    print("B. Unweighted sum across the nine applications, and its cumulation")
    print("=" * 92)
    agg = v.groupby("year")[["P", "CF", "FIX", "MIN3"]].sum()
    agg["CF/P"] = agg["CF"] / agg["P"]
    print(agg.to_string(float_format=lambda x: f"{x:9.4f}"))
    print("\ncumulative:")
    print(agg[["P", "CF", "FIX", "MIN3"]].cumsum().to_string(float_format=lambda x: f"{x:9.4f}"))

    print("\n" + "=" * 92)
    print("C. Why metrics leave the basket")
    print("=" * 92)
    g = f.groupby(["metrics_name", "parent_name"]).agg(
        last=("year", "max"), passed=("threshold", "max"), has_target=("threshold_exists", "max")
    ).reset_index()
    dead = g[g["last"] < 2023]
    print(f"metrics with observations: {len(g)};  dead before 2023: {len(dead)}")
    print(f"  of the dead: passed a declared target  {dead['passed'].notna().sum()}")
    print(f"               had a target, never passed {(dead['has_target'].notna() & dead['passed'].isna()).sum()}")
    print(f"               never declared a target    {dead['has_target'].isna().sum()}")
    print("\ndeaths by final year (a collection event looks like a spike):")
    print(dead.groupby("last").size().to_string())

    print("\n" + "=" * 92)
    print("D. Occupation-level consequences of switching to carry-forward")
    print("=" * 92)
    occupation_comparison(cfg, cf_slopes(f))


if __name__ == "__main__":
    main()
