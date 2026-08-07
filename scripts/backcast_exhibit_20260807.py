#!/usr/bin/env python3
"""Back-cast exhibit: what DAIOE 2010-2023 looks like under the new construction.

Built 7 August 2026. The appendix variant the flagship paper promises, and the honest way to
present a chain point: show the reader what the respecified measure would have said over the
window the paper actually estimates on, rather than only from 2024 forward.

THREE PANELS COMPARED
  P   published        frozen construction, the paper's regressor. Untouched.
  C   capability       human-anchored, information-weighted transform (DESIGN note).
  CM  capability+mean  C, plus allapps as an equal-weight mean over applications present in
                       both t-1 and t (DECISION-allapps note).

The 2024/2025 chain point carries a third change, the LLM-generated 9x58 mapping matrix with
the social discount retired. That matrix is not in the repository (the online appendix records
it as available on request), so this exhibit covers two of the three changes and says so.

WHAT THE EXHIBIT IS FOR. Not to argue the new construction is better, which the paper cannot
adjudicate, but to show what changes and what does not: the level and the time path move a
great deal, the cross-occupation ordering barely moves. A referee who suspects a respecification
was chosen to protect a result can read that off the table directly.

Run:  .venv/bin/python scripts/backcast_exhibit_20260807.py
Writes to reports/backcast_20260807/. Reads data/out; writes nothing into it.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "backcast_20260807"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from daioe import config as cfgmod, stage4_index as s4  # noqa: E402

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("cap", ROOT / "scripts/capability_transform_20260807.py")
cap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cap)

# Okabe-Ito, the lab's palette; safe in greyscale and for colour vision deficiency
BLUE, ORANGE, GREEN = "#0072B2", "#E69F00", "#009E73"
plt.rcParams.update({
    "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.5,
    "figure.dpi": 150, "savefig.bbox": "tight",
})


def _run_stage4(cfg, slopes: pd.DataFrame) -> pd.DataFrame:
    tmp = Path(tempfile.mkdtemp())
    for p in (ROOT / "data/out").glob("*.parquet"):
        shutil.copy(p, tmp / p.name)
    slopes.to_parquet(tmp / "slopes_slimmed_allapps.parquet", index=False)
    raw = dict(cfg.raw)
    raw["paths"] = dict(cfg.raw["paths"])
    raw["paths"]["out"] = str(tmp)
    raw["app_categories"] = ["allapps"]
    panel = s4.build(cfgmod.Config(raw=raw, root=cfg.root))["allapps"]
    shutil.rmtree(tmp)
    return panel


def _both_years_mean(df: pd.DataFrame) -> pd.DataFrame:
    """Equal-weight mean over applications present in both t-1 and t (see DECISION note).

    Base-year exception. The rule excludes an application in the year it enters, which is what
    makes subdomain entry composition-neutral. In the panel's first year every application is
    an entrant by construction, so applying the rule literally zeroes the whole year. The base
    year therefore includes every application present: there is no prior basket to be neutral
    against, and the published index computes that year's progress from metric-level changes
    regardless.
    """
    d = df.copy()
    base_year = d["year"].min()
    present = {(r.parent_name, r.year) for r in d.itertuples()}
    d["_in_both"] = [(p, y - 1) in present or y == base_year
                     for p, y in zip(d["parent_name"], d["year"])]
    d.loc[~d["_in_both"], "mean"] = 0.0
    n = d[d["_in_both"]].groupby("year")["parent_name"].nunique().rename("_N")
    d = d.merge(n, on="year", how="left")
    d["_N"] = d["_N"].fillna(1)
    d["mean"] = (d["mean"] / d["_N"]).astype(np.float32).astype(float)
    return d.drop(columns=["_in_both", "_N"])


def build_panels(cfg):
    base = pd.read_parquet(ROOT / "data/out/slopes_slimmed_allapps.parquet")
    _, appcap = cap.build_capability(cfg)

    cap_slopes = base.merge(appcap[["parent_name", "year", "delta_p"]],
                            on=["parent_name", "year"], how="left")
    cap_slopes["mean"] = (cap_slopes["delta_p"].fillna(0.0).clip(lower=0)
                          .astype(np.float32).astype(float))
    cap_slopes = cap_slopes.drop(columns="delta_p")

    return {
        "P": _run_stage4(cfg, base.copy()),
        "C": _run_stage4(cfg, cap_slopes.copy()),
        "CM": _run_stage4(cfg, _both_years_mean(cap_slopes.copy())),
    }, base, appcap


def comparison_table(panels: dict) -> pd.DataFrame:
    rows = []
    for tag in ("C", "CM"):
        for yr in range(2010, 2024):
            a = panels["P"].query("year == @yr")[["occ_code_onet", "exp_cumul_allapps"]]
            b = panels[tag].query("year == @yr")[["occ_code_onet", "exp_cumul_allapps"]]
            if a.empty or b.empty:
                continue
            j = a.merge(b, on="occ_code_onet", suffixes=("_p", "_v"))
            pa = j["exp_cumul_allapps_p"].rank(pct=True) * 100
            pb = j["exp_cumul_allapps_v"].rank(pct=True) * 100
            top = ((pa > 90) & (pb > 90)).sum() / max((pa > 90).sum(), 1) * 100
            rows.append(dict(
                variant=tag, year=yr,
                level_ratio=j["exp_cumul_allapps_v"].mean() / j["exp_cumul_allapps_p"].mean(),
                spearman=stats.spearmanr(j.iloc[:, 1], j.iloc[:, 2]).statistic,
                mean_pctl_shift=(pb - pa).abs().mean(),
                top_decile_kept=top,
            ))
    return pd.DataFrame(rows)


def fig_progress(base, appcap, path: Path):
    """Cumulative application progress, published against capability, per application."""
    # Both series are restricted to the paper's window and cumulated from 2010. The capability
    # series has pre-2010 observations for some benchmarks (Computer Go runs from 1984), which
    # would otherwise stretch the axis across two decades of empty panel.
    apps = sorted(base["parent_name"].unique())
    short = {"Accurate modelling of human language.": "Language modelling",
             "Language comprehension and question-answering": "Language comprehension and QA",
             "Playing abstract games with extensive hints": "Abstract games",
             "Translation between human langauges": "Translation"}
    fig, axes = plt.subplots(3, 3, figsize=(9.5, 7.0), sharex=True)
    for ax, a in zip(axes.ravel(), apps):
        p = base[(base["parent_name"] == a) & base["year"].between(2010, 2023)].sort_values("year")
        c = appcap[(appcap["parent_name"] == a) & appcap["year"].between(2010, 2023)].sort_values("year")
        ax.plot(p["year"], p["mean"].cumsum(), color=BLUE, lw=1.6, label="published")
        if not c.empty:
            ax.plot(c["year"], c["delta_p"].fillna(0).cumsum(), color=ORANGE, lw=1.6,
                    ls="--", label="capability")
        ax.set_title(short.get(a, a), fontsize=8)
        ax.set_xlim(2010, 2023)
        ax.tick_params(labelsize=7)
    axes.ravel()[0].legend(fontsize=7, frameon=False)
    fig.supylabel("cumulative progress", fontsize=9)
    fig.suptitle("Cumulative AI progress by application: published against human-anchored capability",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_trajectories(panels: dict, path: Path):
    """Seven occupations at fixed percentiles of the 2023 published distribution."""
    p23 = panels["P"].query("year == 2023").copy()
    p23["pct"] = p23["exp_cumul_allapps"].rank(pct=True) * 100
    picks = []
    for q in (0, 10, 25, 50, 75, 90, 100):
        picks.append(p23.iloc[(p23["pct"] - q).abs().argsort().iloc[0]])
    picks = pd.DataFrame(picks)

    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8), sharey=False)
    for ax, tag, title in zip(axes, ("P", "C"),
                              ("Published construction", "Human-anchored capability")):
        for _, r in picks.iterrows():
            s = panels[tag].query("occ_code_onet == @r.occ_code_onet").sort_values("year")
            ax.plot(s["year"], s["exp_cumul_allapps"], lw=1.4,
                    color=plt.cm.viridis(r["pct"] / 100))
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("year")
    axes[0].set_ylabel("cumulative DAIOE")
    fig.suptitle("Exposure trajectories for occupations at the 0th to 100th percentile", fontsize=10)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = cfgmod.load_config(ROOT / "config.yaml")
    panels, base, appcap = build_panels(cfg)

    tab = comparison_table(panels)
    tab.to_csv(OUT / "backcast_comparison.csv", index=False)
    for tag, p in panels.items():
        p.to_parquet(OUT / f"panel_{tag}.parquet", index=False)

    fig_progress(base, appcap, OUT / "fig1_application_progress.pdf")
    fig_trajectories(panels, OUT / "fig2_trajectories.pdf")

    pd.set_option("display.width", 160)
    print("=" * 84)
    print("BACK-CAST: published vs the new construction, 2010-2023")
    print("=" * 84)
    for tag, label in (("C", "capability transform"), ("CM", "capability + both-years mean")):
        s = tab[tab["variant"] == tag]
        print(f"\n--- {label} ---")
        print(s[["year", "level_ratio", "spearman", "mean_pctl_shift", "top_decile_kept"]]
              .to_string(index=False, float_format=lambda x: f"{x:9.4f}"))
    print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    main()
