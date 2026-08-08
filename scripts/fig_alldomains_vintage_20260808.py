"""The all-domains DAIOE figure, sourced from the assembled 2025 vintage.

Reads the vintage build's own slopes panels (data/vintage/vintage_2025_20260808/out),
so what is shown is exactly what the gated release contains: nine frozen applications
plus conversation (ToMBench), software (SWE-bench Verified) and mathematical &
scientific reasoning (GPQA, progress series; exposure awaits the matrix decision).
Agentic task execution remains a placeholder pending the METR licence. Frozen levels
navy; the vintage's spliced 2024-2025 increments vermilion.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
VINTAGE = ROOT / "data" / "vintage" / "vintage_2025_20260808" / "out"
OUT_DIR = ROOT / "reports" / "vintage_2025_20260808"
sys.path.insert(0, str(ROOT / "src"))

from daioe import stage2_ai_progress as s2  # noqa: E402

NAVY, VERMILION, GRAY = "#232b65", "#D55E00", "#8a8a8a"

# --- application-level slopes: frozen (navy) and vintage (vermilion) -------------
frozen_all = pd.read_parquet(ROOT / "data/out/slopes_slimmed_allapps.parquet")
vintage_parts = [pd.read_parquet(VINTAGE / f"slopes_slimmed_{c}.parquet")
                 for c in ("allapps", "conversat", "software", "mathsci")]
vintage = pd.concat(vintage_parts, ignore_index=True)

NEW_PARENTS = {
    "Turing test for casual conversation": "conversation  (ToMBench)",
    "Write computer programs from specifications": "software engineering  (SWE-bench Verified)",
    "Mathematical and scientific reasoning": "maths & science  (GPQA Diamond)",
}
titles = {p: s2._APP_NAME[p] for p in s2._APP_NAME}
titles.update(NEW_PARENTS)


def cum(sl: pd.DataFrame, parent: str, upto: int | None = None) -> pd.DataFrame:
    g = sl[(sl["parent_name"] == parent) & (sl["year"] >= 2010)]
    if upto is not None:
        g = g[g["year"] <= upto]
    if g.empty:
        return g.assign(cumv=[])
    yr = pd.DataFrame({"year": range(int(g["year"].min()), int(g["year"].max()) + 1)})
    m = yr.merge(g[["year", "mean"]], on="year", how="left")
    m["cumv"] = m["mean"].fillna(0.0).cumsum()
    return m


old_parents = sorted(
    (p for p in s2._APP_NAME if s2._APP_ID[s2._APP_NAME[p]] in s2._CATEGORY_IDS["allapps"]),
    key=lambda p: titles[p],
)
order = old_parents + list(NEW_PARENTS)

fig, axes = plt.subplots(4, 4, figsize=(13.5, 11), sharex=True)
axes = axes.ravel()

for ax, parent in zip(axes, order):
    f = cum(frozen_all, parent, upto=2023)
    is_new = parent in NEW_PARENTS
    if len(f):
        ax.plot(f["year"], f["cumv"], color=NAVY, lw=2, solid_capstyle="round")
        base, base_year = float(f["cumv"].iloc[-1]), int(f["year"].iloc[-1])
    else:
        base, base_year = 0.0, 2023
    v = vintage[(vintage["parent_name"] == parent) & (vintage["year"] >= 2024)]
    if len(v):
        yrs = [base_year] + [int(y) for y in v["year"]]
        vals = [base] + list(base + v["mean"].cumsum())
        ax.plot(yrs, vals, color=VERMILION, lw=2, ls=(0, (4, 2)))
    else:
        ax.text(0.97, 0.06, "no post-2023 source", transform=ax.transAxes,
                ha="right", fontsize=7.5, color=GRAY, style="italic")
    ax.axvline(2023, color=GRAY, lw=0.8, alpha=0.5)
    ax.set_title(titles[parent], fontsize=9.5)
    ax.tick_params(labelsize=8)
    ax.xaxis.set_major_locator(plt.MaxNLocator(5, integer=True))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", lw=0.4, alpha=0.3)

# agentic placeholder
ax = axes[len(order)]
ax.set_title("agentic task execution  (METR)", fontsize=9.5)
ax.text(0.5, 0.5, "awaiting METR licence", transform=ax.transAxes, ha="center",
        va="center", fontsize=9, color=GRAY, style="italic")
ax.axvline(2023, color=GRAY, lw=0.8, alpha=0.5)
ax.set_yticks([])
ax.xaxis.set_major_locator(plt.MaxNLocator(5, integer=True))
ax.spines[["top", "right"]].set_visible(False)

# composite: frozen allapps sum construction at application level, spliced
ax = axes[len(order) + 1]
fz = frozen_all[(frozen_all["year"] >= 2010) & (frozen_all["parent_name"] != "robotics")]
ann_f = fz.groupby("year")["mean"].mean()
comp_f = ann_f.cumsum()
ax.plot(comp_f.index, comp_f.values, color=NAVY, lw=2.2)
base = float(comp_f.loc[2023])

def post_comp(parents):
    d = vintage[vintage["parent_name"].isin(parents) & (vintage["year"] >= 2024)]
    annual = d.groupby("year")["mean"].mean()
    return pd.concat([pd.Series([base], index=[2023]), base + annual.cumsum()])

nine = [p for p in old_parents]
seam = post_comp(nine)
ax.plot(seam.index, seam.values, color=VERMILION, lw=2.2, ls=(0, (4, 2)))
seam_all = post_comp(nine + list(NEW_PARENTS))
ax.plot(seam_all.index, seam_all.values, color=VERMILION, lw=1.2, ls=(0, (1, 2)))
ax.text(seam_all.index[-1] + 0.1, seam_all.values[-1], "+3 new\ndomains",
        fontsize=7, color=VERMILION, va="center")
ax.axvline(2023, color=GRAY, lw=0.8, alpha=0.5)
ax.set_title("composite (mean over survivors)", fontsize=9.5)
ax.tick_params(labelsize=8)
ax.xaxis.set_major_locator(plt.MaxNLocator(5, integer=True))
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", lw=0.4, alpha=0.3)

for a in axes[len(order) + 2:]:
    a.set_visible(False)

fig.suptitle("DAIOE, all capability domains — the assembled 2025 vintage: frozen 2010-2023 (navy), "
             "spliced 2024-2025 (vermilion); agentic pending METR", fontsize=11)
fig.supylabel("cumulative application progress", fontsize=9)
handles = [plt.Line2D([], [], color=NAVY, lw=2, label="frozen 2010-2023"),
           plt.Line2D([], [], color=VERMILION, lw=2, ls=(0, (4, 2)),
                      label="2025 vintage, spliced 2024-2025")]
fig.legend(handles=handles, loc="lower right", fontsize=8.5, frameon=False)
fig.tight_layout(rect=(0, 0.01, 1, 0.965))
out = OUT_DIR / "fig_daioe_alldomains_vintage2025.png"
fig.savefig(out, dpi=200)
print(f"wrote {out}")
