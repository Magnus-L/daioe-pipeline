#!/usr/bin/env python3
"""Build the three local exhibits for the AI Unboxed revision (Phase B).

None of this needs MONA or register access: everything reads the frozen 2023
baseline panels in data/out/. Outputs go straight into the paper's Fig-n-tables/
folder, which the manuscript loads with \\tblinput and \\includegraphics.

  1. T02, "the dynamic layer is incremental". The draft concedes that the
     2010-2023 long difference and the 2023 level correlate at 1.00 and stops
     there. The concession is right and stays, but it is not the whole story:
     the cross-sectional ORDERING moves a great deal mid-sample, and the annual
     increment re-ranks harder still. A referee cannot call that "almost
     identical to the static level".

  2. T15, validation, which also resolves a live contradiction. The main text
     says DAIOE correlates strongly with "both FRS18 and FRS21"; the appendix
     reports Spearman 0.12 for FRS18. The honest pattern is that DAIOE tracks
     Felten and Eloundou, is orthogonal to Webb and FRS18, and is NEGATIVELY
     rank-correlated with Frey-Osborne, which is what a routine-automation
     measure should do. Better argued by us than discovered by a referee.

  3. The delta grid figure, from the round-5 B8 regression coefficients, so the
     reader sees the sensitivity of the estimate to the social-skill discount
     parameter rather than a referee plotting it themselves. delta = 2 is
     inherited from the published construction; it was not selected here.

Run: python scripts/build_paper_exhibits_20260803.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "out"
FIGDIR = Path.home() / "Documents/Workspace/projects/daioe/paper/Fig-n-tables"

# Round-5 B8 variant grid, firm + industry-year FE, from
# projects/daioe/mona-batch/results/rev_B8_variants.txt
DELTA_GRID = [
    ("0.5",  -0.3055, 0.2431),
    ("1",   -0.7850, 0.3533),
    ("2",   -0.9512, 0.3130),
    ("4",   -0.7986, 0.2314),
    ("none", -0.5670, 0.1519),
]
PAPER_DELTA = "2"


def tex_escape(s: str) -> str:
    return s.replace("&", r"\&").replace("_", r"\_").replace("%", r"\%")


# ---------------------------------------------------------------- T02
def build_t02() -> pd.DataFrame:
    """Re-ranking evidence at ONET level, where the panel is richest."""
    df = pd.read_stata(OUT / "daioe_panel_onet.dta")[
        ["occ_code_onet", "year", "exp_cumul_allapps", "exp_change_allapps"]
    ].copy()
    df["year"] = df["year"].astype(int)

    wide_lvl = df.pivot(index="occ_code_onet", columns="year", values="exp_cumul_allapps")
    wide_chg = df.pivot(index="occ_code_onet", columns="year", values="exp_change_allapps")
    years = sorted(y for y in wide_lvl.columns)
    final = max(years)

    rows = []
    for y in years:
        lvl = spearmanr(wide_lvl[y], wide_lvl[final], nan_policy="omit").statistic
        chg = spearmanr(wide_chg[y], wide_chg[final], nan_policy="omit").statistic
        rows.append(
            {
                "year": y,
                "rho_level": lvl,
                "rho_increment": chg,
                "mean_increment": df.loc[df.year == y, "exp_change_allapps"].mean(),
            }
        )
    t = pd.DataFrame(rows)

    # the concession the draft already makes, recomputed so the note is exact
    ld = wide_lvl[final] - wide_lvl[min(years)]
    pear = np.corrcoef(ld.dropna(), wide_lvl[final].loc[ld.dropna().index])[0, 1]
    spear = spearmanr(ld, wide_lvl[final], nan_policy="omit").statistic
    base_mean = wide_lvl[min(years)].mean()

    print("\n=== T02 ===")
    print(f"  n occupations = {wide_lvl.shape[0]}")
    print(f"  corr(long difference {min(years)}-{final}, level {final}): "
          f"Pearson {pear:.6f}, Spearman {spear:.6f}")
    print(f"  mean {min(years)} exposure = {base_mean:.4f} (small, NOT zero)")
    print(t.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    lines = ["{", r"\begin{tabular}{lccc}", r"\hline\hline",
             r"Year & \multicolumn{1}{c}{Level vs.\ 2023} & "
             r"\multicolumn{1}{c}{Increment vs.\ 2023} & "
             r"\multicolumn{1}{c}{Mean increment} \\",
             r"\hline"]
    for _, r in t.iterrows():
        lines.append(f"{int(r.year)} & {r.rho_level:.3f} & {r.rho_increment:.3f} & "
                     f"{r.mean_increment:.3f} \\\\")
    lines += [r"\hline\hline", r"\end{tabular}", "}"]
    (FIGDIR / "t02_rerank.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  wrote {FIGDIR/'t02_rerank.tex'}")
    return t


# ---------------------------------------------------------------- T15
def build_t15() -> pd.DataFrame:
    """Top-decile overlap and rank correlation against every comparator."""
    df = pd.read_stata(OUT / "daioe_panel_soc.dta")
    df = df[df.year == 2023].copy()

    comparators = [
        ("frs21_aioe", "Felten et al.\\ (2021), AIOE"),
        # E1+E2 is the declared primary Open24 variant (Erik's confirmation by email,
        # 11 Aug 2026; the paper's footnote and the OA ISCO table already say E1+E2).
        # The GPT and human-E1 rows are retained for diagnostics; re-enable to print.
        ("open24_human_E1_E2", "Eloundou et al.\\ (2024), human E1+E2"),
        # ("open24_gpt_automation", "Eloundou et al.\\ (2024), GPT"),
        # ("open24_human_E1", "Eloundou et al.\\ (2024), human E1"),
        # Webb year follows the bibitem (Webb 2019, SSRN 3482150), not the circulating
        # 2020 vintage label; harmonised 11 Aug 2026 with the paper and OA.
        ("webb19_ai_score", "Webb (2019), AI"),
        ("frs18_index_original", "Felten et al.\\ (2018), original"),
        ("frs18_index_new_weights", "Felten et al.\\ (2018), reweighted"),
        ("fo17_p_computerisation", "Frey and Osborne (2017)"),
    ]

    rows = []
    for col, label in comparators:
        if col not in df.columns:
            print(f"  MISSING: {col}")
            continue
        sub = df[["exp_cumul_allapps", col]].dropna()
        n = len(sub)
        rho = spearmanr(sub["exp_cumul_allapps"], sub[col]).statistic
        k = max(1, int(round(n / 10)))
        top_d = set(sub.nlargest(k, "exp_cumul_allapps").index)
        top_c = set(sub.nlargest(k, col).index)
        rows.append({"label": label, "n": n, "rho": rho,
                     "overlap": len(top_d & top_c), "k": k,
                     "pct": 100 * len(top_d & top_c) / k})
    t = pd.DataFrame(rows)

    print("\n=== T15 ===")
    print(t.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    lines = ["{", r"\begin{tabular}{lccc}", r"\hline\hline",
             r"Measure & \multicolumn{1}{c}{Occupations} & "
             r"\multicolumn{1}{c}{Rank corr.} & "
             r"\multicolumn{1}{c}{Top-decile overlap} \\",
             r"\hline"]
    for _, r in t.iterrows():
        lines.append(f"{r.label} & {int(r.n)} & {r.rho:.3f} & "
                     f"{int(r.overlap)}/{int(r.k)} ({r.pct:.0f}\\%) \\\\")
    lines += [r"\hline\hline", r"\end{tabular}", "}"]
    (FIGDIR / "t15_validation.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  wrote {FIGDIR/'t15_validation.tex'}")
    return t


# ---------------------------------------------------------------- delta grid
def build_delta_figure() -> None:
    """Dot-and-whisker over an ordered parameter. One series, so no legend."""
    labels = [d[0] for d in DELTA_GRID]
    coef = np.array([d[1] for d in DELTA_GRID])
    se = np.array([d[2] for d in DELTA_GRID])
    lo, hi = coef - 1.96 * se, coef + 1.96 * se
    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    ax.axhline(0, color="0.65", linewidth=0.8, zorder=1)

    # greyscale by design: the paper prints in black and white
    for i in range(len(x)):
        is_paper = labels[i] == PAPER_DELTA
        ax.vlines(x[i], lo[i], hi[i], color="0.35", linewidth=1.4, zorder=2)
        ax.plot(x[i], coef[i], marker="o", markersize=7 if is_paper else 5.5,
                color="black", markerfacecolor="black" if is_paper else "white",
                markeredgewidth=1.4, zorder=3)

    ax.set_xticks(x)
    ax.set_xticklabels([r"$\delta=0.5$", r"$\delta=1$", r"$\delta=2$",
                        r"$\delta=4$", "no discount"])
    ax.set_ylabel("Coefficient on lagged DAIOE")
    ax.set_xlim(-0.5, len(x) - 0.5)

    # direct label on the paper's own parameter only, not on every point
    i = labels.index(PAPER_DELTA)
    ax.annotate("published\nconstruction", xy=(x[i], coef[i]),
                xytext=(x[i] + 0.18, coef[i] - 0.42), fontsize=8,
                color="0.25", ha="left",
                arrowprops=dict(arrowstyle="-", color="0.55", linewidth=0.7))

    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("0.5")
        ax.spines[s].set_linewidth(0.8)
    ax.tick_params(colors="0.3", labelsize=9, length=3)
    ax.yaxis.grid(True, color="0.9", linewidth=0.6)
    ax.set_axisbelow(True)

    fig.tight_layout()
    out = FIGDIR / "daioe_delta_grid.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"\n=== delta grid ===\n  wrote {out}")
    for l, c, s in zip(labels, coef, se):
        print(f"  delta={l:>4}: {c:+.4f} ({s:.4f})  95% CI [{c-1.96*s:+.3f}, {c+1.96*s:+.3f}]")


def main() -> None:
    if not FIGDIR.exists():
        raise SystemExit(f"paper figure folder not found: {FIGDIR}")
    build_t02()
    build_t15()
    build_delta_figure()
    print("\ndone.")


if __name__ == "__main__":
    main()
