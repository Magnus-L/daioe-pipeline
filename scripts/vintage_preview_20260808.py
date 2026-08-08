"""Seam preview for the 2025 vintage: does appending 2024-2025 look strange?

Magnus's question before the vintage assembly (8 Aug 2026): what does DAIOE's capture
of AI progress look like in the frozen 2010-2023 vintage, what will it look like with
2024-2025 appended, and will there be an odd break?

Two runs of the published construction, in memory only (no data/out writes):

  FROZEN    config.yaml as shipped, year_final 2023, no updates. Bit-exact baseline.
  EXTENDED  config-refresh2024.yaml inputs + year_final 2025 + the Epoch refresh
            workbook + both extension workbooks (GPQA, ToMBench). This is the full
            set of admissible post-2023 observations as of today; 2026 exists only
            for GPQA and is a partial year, excluded on the Track B correction.

The figure shows the VINTAGE object under the settled seam policy (checkpoint2,
decision 2026-07-07: freeze history, vintage-splice at 2023): frozen cumulative
levels through 2023 in navy, then the extended run's 2024-2025 increments chained
onto the frozen 2023 level, dashed vermilion. The extended run's own 2010-2023
history differs from the frozen series (the PwC backfill revises history; 1,289
backfill rows), but the seam audit showed the 2024 increment is seam-insensitive
(at most 0.53% depends on revision), which is what makes the splice safe. The
composite panel shows allapps under the published mean-over-survivors rule, plus a
variant including conversation, which previews the assembly decision.

Output: reports/vintage_preview_20260808/{fig_vintage_preview.png,.pdf} and a
printed per-application table of 2024/2025 progress against the frozen-window
annual range (the "is the seam inside historical variation?" check).
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daioe import config as cfgmod  # noqa: E402
from daioe import stage2_ai_progress as s2  # noqa: E402

OUT = ROOT / "reports" / "vintage_preview_20260808"
OUT.mkdir(exist_ok=True)

NAVY = "#232b65"      # frozen window (lab brand navy)
VERMILION = "#D55E00"  # appended years (Okabe-Ito vermilion; blue-orange CVD axis)
GRAY = "#8a8a8a"

ALLAPPS_PARENTS = [p for p, a in s2._APP_NAME.items()
                   if s2._APP_ID[a] in s2._CATEGORY_IDS["allapps"]]
CONV_PARENT = "Turing test for casual conversation"


def _slopes(raw: dict) -> pd.DataFrame:
    cfg = cfgmod.Config(raw=raw, root=ROOT)
    measures = s2._build_measures(cfg)
    formated = s2.build_formated_data(cfg)
    frontiers = s2.build_metrics_frontiers(cfg, formated, measures)
    sl = s2.build_slopes(cfg, frontiers)
    return sl[sl["parent_name"] != "robotics"]


def build_panels() -> tuple[pd.DataFrame, pd.DataFrame]:
    frozen_raw = yaml.safe_load((ROOT / "config.yaml").read_text())
    ext_raw = yaml.safe_load((ROOT / "config-refresh2024.yaml").read_text())
    ext_raw["year_final"] = 2025
    ext_raw["benchmark_updates"] = [
        "data/updates/measures_updates_2024plus.xlsx",
        "data/updates/measures_updates_epoch_2026-08-07.xlsx",
    ]
    ext_raw["benchmark_extensions"] = [
        "data/updates/extension_gpqa_2026-08-07.xlsx",
        "data/updates/extension_tombench_2026-08-08.xlsx",
    ]
    frozen = _slopes(frozen_raw)
    extended = _slopes(ext_raw)
    return frozen, extended


def cumulate(sl: pd.DataFrame) -> pd.DataFrame:
    """Cumulative application progress, on a year grid starting at each parent's
    first observed year (a series is silent before its data begin, not zero).

    Years in which an application has no contributing benchmark add zero progress
    (the panel simply carries its level), which is exactly how the published
    construction treats them: absent from the mean, not negative.
    """
    df = sl[(sl["year"] >= 2010)][["parent_name", "year", "mean", "count"]].copy()
    grids = []
    for p, g in df.groupby("parent_name"):
        first = int(g["year"].min())
        yr = pd.DataFrame({"year": range(first, int(df["year"].max()) + 1)})
        yr["parent_name"] = p
        m = yr.merge(g, on=["parent_name", "year"], how="left")
        m["cum"] = m["mean"].fillna(0.0).cumsum()
        grids.append(m)
    return pd.concat(grids, ignore_index=True)


def splice(f: pd.DataFrame, e: pd.DataFrame) -> pd.DataFrame:
    """Chain the extended run's post-2023 increments onto the frozen 2023 level.

    This IS the vintage under the settled seam policy: published history immutable,
    2024+ increments computed on the archive's fuller frontier, linked at 2023.
    For a parent absent from the frozen run (conversation) the chain base is zero
    at the chain point.
    """
    out = []
    for p, g in e.groupby("parent_name"):
        fro = f[f["parent_name"] == p]
        base = float(fro.loc[fro["year"] == 2023, "cum"].iloc[0]) if len(fro) else 0.0
        post = g[g["year"] >= 2024].copy()
        post["cum"] = base + post["mean"].fillna(0.0).cumsum()
        seam = pd.DataFrame(
            {"parent_name": [p], "year": [2023], "mean": [float("nan")],
             "count": [float("nan")], "cum": [base]}
        )
        out.append(pd.concat([seam, post], ignore_index=True))
    return pd.concat(out, ignore_index=True)


def composite(sl: pd.DataFrame, parents: list[str]) -> pd.Series:
    """allapps as published: each year, the mean over the applications PRESENT
    (mean-over-survivors; the settled basket rule), then cumulated."""
    d = sl[sl["parent_name"].isin(parents) & (sl["year"] >= 2010)]
    annual = d.groupby("year")["mean"].mean()
    grid = pd.Series(0.0, index=range(2010, int(sl["year"].max()) + 1))
    grid.loc[annual.index] = annual
    return grid.cumsum()


def main() -> None:
    frozen, extended = build_panels()
    fc, ec = cumulate(frozen), cumulate(extended)

    order = sorted(ALLAPPS_PARENTS, key=lambda p: s2._APP_NAME[p]) + [CONV_PARENT]
    fig, axes = plt.subplots(3, 4, figsize=(13, 8.5), sharex=True)
    axes = axes.ravel()

    sp = splice(fc, ec)
    for ax, parent in zip(axes, order):
        app = s2._APP_NAME[parent]
        f = fc[fc["parent_name"] == parent]
        v = sp[sp["parent_name"] == parent]
        if len(f):
            ax.plot(f["year"], f["cum"], color=NAVY, lw=2, solid_capstyle="round")
        if len(v):
            ax.plot(v["year"], v["cum"], color=VERMILION, lw=2, ls=(0, (4, 2)))
        ax.axvline(2023, color=GRAY, lw=0.8, alpha=0.5)
        # flag panels with no post-2023 observations
        has_post = v["mean"].notna().any() if len(v) else False
        if not has_post:
            ax.text(0.97, 0.06, "no post-2023 source", transform=ax.transAxes,
                    ha="right", fontsize=7.5, color=GRAY, style="italic")
        ax.set_title(app, fontsize=9.5)
        ax.tick_params(labelsize=8)
        ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", lw=0.4, alpha=0.3)

    # composite panel, last slot: frozen composite, then spliced 2024-25 increments
    ax = axes[len(order)]
    ca_f = composite(frozen, ALLAPPS_PARENTS)
    base = float(ca_f.loc[2023])

    def _post(parents: list[str]) -> pd.Series:
        d = extended[extended["parent_name"].isin(parents) & (extended["year"] >= 2024)]
        annual = d.groupby("year")["mean"].mean()
        s = pd.Series([base], index=[2023])
        return pd.concat([s, base + annual.cumsum()])

    ax.plot(ca_f.index, ca_f.values, color=NAVY, lw=2.2)
    seam = _post(ALLAPPS_PARENTS)
    ax.plot(seam.index, seam.values, color=VERMILION, lw=2.2, ls=(0, (4, 2)))
    seam_c = _post(ALLAPPS_PARENTS + [CONV_PARENT])
    ax.plot(seam_c.index, seam_c.values, color=VERMILION, lw=1.2, ls=(0, (1, 2)))
    ax.text(seam_c.index[-1] + 0.1, seam_c.values[-1], "+conv", fontsize=7.5,
            color=VERMILION, va="center")
    ax.axvline(2023, color=GRAY, lw=0.8, alpha=0.5)
    ax.set_title("allapps composite (mean over survivors)", fontsize=9.5)
    ax.tick_params(labelsize=8)
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", lw=0.4, alpha=0.3)

    for ax in axes[len(order) + 1:]:
        ax.set_visible(False)

    fig.suptitle("DAIOE cumulative AI progress by application: frozen 2010-2023 (navy) "
                 "and the 2025 vintage's spliced 2024-2025 increments (vermilion, dashed)",
                 fontsize=11)
    fig.supylabel("cumulative application progress", fontsize=9)
    handles = [plt.Line2D([], [], color=NAVY, lw=2, label="frozen 2010-2023"),
               plt.Line2D([], [], color=VERMILION, lw=2, ls=(0, (4, 2)),
                          label="appended 2024-2025")]
    fig.legend(handles=handles, loc="lower right", fontsize=8.5, frameon=False)
    fig.tight_layout(rect=(0, 0.01, 1, 0.96))
    for suffix in ("png", "pdf"):
        fig.savefig(OUT / f"fig_vintage_preview.{suffix}", dpi=200)
    print(f"wrote {OUT.relative_to(ROOT)}/fig_vintage_preview.png/.pdf")

    # ---- the seam-in-historical-range table -------------------------------------
    rows = []
    for parent in order:
        app = s2._APP_NAME[parent]
        f = frozen[(frozen["parent_name"] == parent) & (frozen["year"] >= 2010)]
        e = extended[extended["parent_name"] == parent]
        hist = f["mean"]
        r = {
            "application": app,
            "hist mean": hist.mean() if len(hist) else float("nan"),
            "hist min": hist.min() if len(hist) else float("nan"),
            "hist max": hist.max() if len(hist) else float("nan"),
        }
        for yr in (2024, 2025):
            v = e[e["year"] == yr]
            r[f"{yr} prog"] = v["mean"].iloc[0] if len(v) else float("nan")
            r[f"{yr} n"] = int(v["count"].iloc[0]) if len(v) else 0
        rows.append(r)
    tab = pd.DataFrame(rows)
    pd.set_option("display.width", 160)
    print("\nAnnual application progress: appended years against the frozen-window range")
    print(tab.round(3).to_string(index=False))
    tab.to_csv(OUT / "seam_table.csv", index=False)


if __name__ == "__main__":
    main()
