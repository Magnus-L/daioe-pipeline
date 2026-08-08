"""T02: what does the "D" in DAIOE add? Quantified concession, then evidence.

The critique (EJ R2 sharpest; RS3, EJ editor, EJ R3): in a long difference the dynamic
measure is nearly the static end-year level, so the contribution over Felten et al.'s
static AIOE is unclear. The evidence-based answer has three parts, all public data:

  C   CONCEDE WITH THE NUMBER. Across occupations, corr(DAIOE_2023 - DAIOE_2010,
      DAIOE_2023) is computed and reported; it is close to one because 2010 levels are
      near zero. The long-difference specification therefore cannot be what
      distinguishes the measure, and the paper should not pretend otherwise. What
      distinguishes it is the within-occupation TIMING variation, which no static
      measure possesses. Also reported: corr with Felten's static AIOE (frs21_aioe).

  E1  HOW MUCH TIMING VARIATION IS THERE? A rank-one (SVD) decomposition of the
      occupation-year panel: a static-ranking-times-common-trend approximation
      f_o x g_t captures most of the LEVEL variance (reported), but a much smaller
      share of the variance in ANNUAL CHANGES (reported): the residual is
      occupation-specific timing. Its economic shape: the year by which an occupation
      reaches half of its 2023 exposure spans [P10, P90] years across occupations.

  E2  THE TIMING IS THE TECHNOLOGY CHRONOLOGY. Normalised cumulative subdomain
      progress curves reproduce the documented sequence: vision-era progress
      concentrates early (post-2012), speech mid-decade, language modelling after
      2017. The dynamic component is not noise around a trend; it is the recorded
      history of AI, which is checkable against sources outside the measure.

  E3  THE TIMING PREDICTS. Swedish job advertisements (JobTech, CC0; the AIEL
      monitor's distinct-advertisement unit) give an occupation-YEAR outcome: the
      share of ads mentioning AI. With occupation AND year fixed effects, the
      within variation of DAIOE predicts the within variation of AI demand: the
      common AI boom and every static ranking are absorbed, so the surviving
      coefficient is differential timing matching differential timing. A static
      exposure measure is a constant within occupation and cannot enter this
      regression at all. As a falsification, the rank-one approximation of DAIOE
      (static ranking x common trend) is entered in the same specification. The
      occupation-level ads series exists from 2020, so the window is 2020-2023:
      the generative window, exactly where the referee's concern lives.

Outputs: reports/t02_dynamic_content_20260808/ (RESULTS.md + figures).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "t02_dynamic_content_20260808"
OUT.mkdir(exist_ok=True)

import sys

sys.path.insert(0, str(ROOT / "src"))
from daioe import io as dio  # noqa: E402
from daioe import stage2_ai_progress as s2  # noqa: E402

ADS = Path.home() / ("Documents/Workspace/lab-infrastructure/ai-monitor/data/"
                     "bulk_v1/derived/series_ssyk4.csv")

NAVY, VERMILION, GREEN, GRAY = "#232b65", "#D55E00", "#009E73", "#8a8a8a"


# --------------------------------------------------------------- C: the concession
def concession() -> dict:
    soc = dio.read_dta(ROOT / "data/out/daioe_panel_soc.dta")
    lvl23 = soc[soc["year"] == 2023].set_index("occ_code_soc")
    lvl10 = soc[soc["year"] == 2010].set_index("occ_code_soc")["exp_cumul_allapps"]
    ld = (lvl23["exp_cumul_allapps"] - lvl10).dropna()
    both = pd.concat([ld.rename("longdiff"),
                      lvl23["exp_cumul_allapps"].rename("level23"),
                      lvl23["frs21_aioe"].rename("aioe")], axis=1).dropna()
    return {
        "corr_longdiff_level23": round(float(both["longdiff"].corr(both["level23"])), 4),
        "spearman_level23_felten": round(float(
            stats.spearmanr(both["level23"], both["aioe"])[0]), 3),
        "n": int(len(both)),
    }


# ------------------------------------------------- E1: rank-one decomposition + timing
def rank_one() -> dict:
    onet = dio.read_dta(ROOT / "data/out/daioe_panel_onet.dta")
    piv = onet.pivot_table(index="occ_code_onet", columns="year",
                           values="exp_cumul_allapps").dropna()
    X = piv.values
    U, S, Vt = np.linalg.svd(X - 0, full_matrices=False)
    lvl_share = float(S[0] ** 2 / (S ** 2).sum())
    D = np.diff(X, axis=1)
    Ud, Sd, Vtd = np.linalg.svd(D, full_matrices=False)
    chg_share = float(Sd[0] ** 2 / (Sd ** 2).sum())
    # timing: year reaching half the 2023 level
    final = X[:, -1]
    ok = final > 0
    years = piv.columns.values.astype(float)
    half_year = np.array([years[np.argmax(X[i] >= 0.5 * final[i])] for i in range(len(X))])
    hy = half_year[ok]
    return {
        "rank1_share_levels": round(lvl_share, 3),
        "rank1_share_changes": round(chg_share, 3),
        "halfyear_p10": float(np.percentile(hy, 10)),
        "halfyear_p50": float(np.percentile(hy, 50)),
        "halfyear_p90": float(np.percentile(hy, 90)),
        "n_occ": int(ok.sum()),
    }


# ------------------------------------- E1b: subdomain timing heterogeneity (the unboxing)
def subdomain_curves() -> dict:
    """The composite is near rank-one; the SUBDOMAIN timing curves are not one curve.
    Pairwise correlations of the nine subdomains' annual application-progress paths."""
    sl = pd.read_parquet(ROOT / "data/out/slopes_slimmed_allapps.parquet")
    sl = sl[(sl["year"] >= 2010) & (sl["parent_name"] != "robotics")]
    piv = sl.pivot_table(index="year", columns="parent_name", values="mean").fillna(0.0)
    C = piv.corr().values
    off = C[~np.eye(len(C), dtype=bool)]
    # rank-one share of the stacked subdomain-change structure
    Xs = piv.values.T  # subdomain x year annual progress
    Us, Ss, Vts = np.linalg.svd(Xs - Xs.mean(axis=1, keepdims=True), full_matrices=False)
    return {"pairwise_corr_min": round(float(off.min()), 2),
            "pairwise_corr_median": round(float(np.median(off)), 2),
            "pairwise_corr_max": round(float(off.max()), 2),
            "rank1_share_subdomain_paths": round(float(Ss[0] ** 2 / (Ss ** 2).sum()), 3)}


# ----------------------------------------------------- E2: the chronology of subdomains
def chronology() -> None:
    sl = pd.read_parquet(ROOT / "data/out/slopes_slimmed_allapps.parquet")
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    marks = {2012: "AlexNet", 2016: "AlphaGo", 2017: "Transformer", 2020: "GPT-3",
             2022: "ChatGPT"}
    show = {"Image classification": NAVY, "Speech Recognition": GREEN,
            "Accurate modelling of human language.": VERMILION}
    for parent, colr in show.items():
        g = sl[(sl["parent_name"] == parent) & (sl["year"] >= 2010)].sort_values("year")
        cum = g["mean"].cumsum()
        ax.plot(g["year"], cum / cum.iloc[-1], color=colr, lw=2,
                label=s2._APP_NAME[parent])
    for k, (yr, lab) in enumerate(marks.items()):
        ax.axvline(yr, color=GRAY, lw=0.7, alpha=0.5)
        ax.text(yr, 1.02 + 0.045 * (k % 2), lab, rotation=0, fontsize=7,
                ha="center", color=GRAY)
    ax.set_ylabel("share of 2010-2023 progress accrued", fontsize=9)
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    ax.tick_params(labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(lw=0.4, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "fig_t02_chronology.png", dpi=200)
    fig.savefig(OUT / "fig_t02_chronology.pdf")
    plt.close(fig)


# --------------------------------------------- E3: within-occupation timing prediction
def within_prediction() -> dict:
    ads = pd.read_csv(ADS)
    ads = ads.dropna(subset=["ssyk4"]).copy()
    ads["ssyk4"] = ads["ssyk4"].astype(float).astype(int).astype(str).str.zfill(4)
    ads = ads[ads["year"].astype(str).str.fullmatch(r"\d{4}")]  # annual rows only
    ads["year"] = ads["year"].astype(int)
    ads = ads[(ads["year"] >= 2020) & (ads["year"] <= 2023)]  # occupation-level ads exist 2020+
    ads["ai_share"] = ads["ai_any"] / ads["total"]

    ssyk = dio.read_dta(ROOT / "data/out/Publication/daioe_ssyk2012.dta")
    ssyk = ssyk.copy()
    ssyk["ssyk4"] = ssyk["ssyk2012_4"].astype(float).astype(int).astype(str).str.zfill(4)
    d = ads.merge(ssyk[["ssyk4", "year", "daioe_allapps"]], on=["ssyk4", "year"])

    # volume screen: occupations with thin ad counts have noisy shares
    vol = d.groupby("ssyk4")["total"].min()
    keep = vol[vol >= 100].index
    d = d[d["ssyk4"].isin(keep)]
    # balanced panel for exact two-way demeaning
    cnt = d.groupby("ssyk4")["year"].count()
    d = d[d["ssyk4"].isin(cnt[cnt == 4].index)].copy()

    def twoway(col: str) -> pd.Series:
        x = d.set_index(["ssyk4", "year"])[col]
        return (x - x.groupby("ssyk4").transform("mean")
                - x.groupby("year").transform("mean") + x.mean())

    y = twoway("ai_share")
    x = twoway("daioe_allapps")
    # rank-one falsification regressor: static 2023 ranking x common year path
    d23 = d[d["year"] == 2023].set_index("ssyk4")["daioe_allapps"]
    gt = d.groupby("year")["daioe_allapps"].mean()
    d["rank1"] = d["ssyk4"].map(d23) / d23.mean() * d["year"].map(gt)
    x1 = twoway("rank1")

    def fe_reg(xv: pd.Series) -> dict:
        b = float((xv * y).sum() / (xv * xv).sum())
        resid = y - b * xv
        # cluster by occupation
        cl = pd.DataFrame({"xu": xv * resid, "g": [i[0] for i in xv.index]})
        meat = (cl.groupby("g")["xu"].sum() ** 2).sum()
        se = float(np.sqrt(meat) / (xv * xv).sum())
        r2 = float(1 - (resid ** 2).sum() / (y ** 2).sum())
        return {"beta": round(b, 4), "se": round(se, 4),
                "t": round(b / se, 2), "within_r2": round(r2, 4)}

    raw = fe_reg(x)
    r1 = fe_reg(x1)
    n_occ = d["ssyk4"].nunique()
    xy = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
    rho_w = float(stats.pearsonr(xy["x"], xy["y"])[0])
    return {"n_occupations": int(n_occ), "n_obs": int(len(d)),
            "within_corr": round(rho_w, 3), "daioe": raw, "rank1_falsification": r1}


# ------------------------- E3b: subdomain horse race on AI-demand growth, 2020-2023
def subdomain_horserace() -> dict:
    """Cross-occupation long difference over the generative window: does the subdomain
    whose capability moved (genai) predict AI-demand growth, against one whose
    capability had plateaued (image recognition)? A static composite cannot even pose
    this question; subdomain timing is what poses it."""
    ads = pd.read_csv(ADS).dropna(subset=["ssyk4"])
    ads["ssyk4"] = ads["ssyk4"].astype(float).astype(int).astype(str).str.zfill(4)
    ads = ads[ads["year"].astype(str).str.fullmatch(r"\d{4}")]
    ads["year"] = ads["year"].astype(int)
    ads["ai_share"] = ads["ai_any"] / ads["total"]
    ssyk = dio.read_dta(ROOT / "data/out/Publication/daioe_ssyk2012.dta").copy()
    ssyk["ssyk4"] = ssyk["ssyk2012_4"].astype(float).astype(int).astype(str).str.zfill(4)

    def wide(col, yr):
        s = ssyk[ssyk["year"] == yr].set_index("ssyk4")[col]
        return s

    a20 = ads[ads["year"] == 2020].set_index("ssyk4")
    a23 = ads[ads["year"] == 2023].set_index("ssyk4")
    df = pd.DataFrame({
        "d_ads": a23["ai_share"] - a20["ai_share"],
        "vol": np.minimum(a20["total"], a23["total"]),
        "d_genai": wide("daioe_genai", 2023) - wide("daioe_genai", 2020),
        "d_imgrec": wide("daioe_imgrec", 2023) - wide("daioe_imgrec", 2020),
    }).dropna()
    df = df[df["vol"] >= 100]
    z = (df[["d_genai", "d_imgrec"]] - df[["d_genai", "d_imgrec"]].mean()) / df[
        ["d_genai", "d_imgrec"]].std()
    X = np.column_stack([np.ones(len(df)), z["d_genai"], z["d_imgrec"]])
    yv = df["d_ads"].values * 100  # percentage points
    b, *_ = np.linalg.lstsq(X, yv, rcond=None)
    e = yv - X @ b
    XtX_inv = np.linalg.inv(X.T @ X)
    meat = (X * e[:, None]).T @ (X * e[:, None])
    V = XtX_inv @ meat @ XtX_inv * len(df) / (len(df) - X.shape[1])
    se = np.sqrt(np.diag(V))
    rho = {k: round(float(stats.spearmanr(df[k], df["d_ads"])[0]), 3)
           for k in ("d_genai", "d_imgrec")}
    return {"n": int(len(df)),
            "beta_genai_pp_per_sd": round(float(b[1]), 3), "t_genai": round(float(b[1] / se[1]), 2),
            "beta_imgrec_pp_per_sd": round(float(b[2]), 3), "t_imgrec": round(float(b[2] / se[2]), 2),
            "spearman": rho}


def main() -> None:
    c = concession()
    e1 = rank_one()
    chronology()
    e3 = within_prediction()
    e1b = subdomain_curves()
    e3b = subdomain_horserace()

    rep = OUT / "RESULTS.md"
    with open(rep, "w") as fh:
        fh.write("# T02: what the dynamic component adds — results (8 Aug 2026)\n\n")
        fh.write("## C. The concession, quantified\n")
        fh.write(f"- corr(long difference 2010-2023, 2023 level) = "
                 f"{c['corr_longdiff_level23']} (n={c['n']} SOC occupations)\n")
        fh.write(f"- Spearman(DAIOE 2023 level, Felten AIOE) = "
                 f"{c['spearman_level23_felten']}\n\n")
        fh.write("## E1. Rank-one (static ranking x common trend) decomposition\n")
        fh.write(f"- share of LEVEL variance captured: {e1['rank1_share_levels']}\n")
        fh.write(f"- share of ANNUAL-CHANGE variance captured: "
                 f"{e1['rank1_share_changes']}\n")
        fh.write(f"- year reaching half of 2023 exposure: P10 {e1['halfyear_p10']:.0f}, "
                 f"median {e1['halfyear_p50']:.0f}, P90 {e1['halfyear_p90']:.0f} "
                 f"({e1['n_occ']} occupations)\n\n")
        fh.write("## E1b. Subdomain timing heterogeneity (the unboxing)\n")
        fh.write(f"- pairwise correlations of the nine subdomains' annual progress paths: "
                 f"min {e1b['pairwise_corr_min']}, median {e1b['pairwise_corr_median']}, "
                 f"max {e1b['pairwise_corr_max']}\n")
        fh.write(f"- rank-one share of the subdomain path family: "
                 f"{e1b['rank1_share_subdomain_paths']}\n\n")
        fh.write("## E3. Within-occupation timing prediction (Swedish job ads)\n")
        fh.write(f"- panel: {e3['n_occupations']} SSYK4 occupations x 4 years (2020-2023) "
                 f"(balanced, min 100 ads/yr), n={e3['n_obs']}\n")
        fh.write(f"- two-way-FE within correlation: {e3['within_corr']}\n")
        fh.write(f"- DAIOE (occ+year FE, occ-clustered): beta={e3['daioe']['beta']}, "
                 f"t={e3['daioe']['t']}, within-R2={e3['daioe']['within_r2']}\n")
        fh.write(f"- rank-one falsification: beta={e3['rank1_falsification']['beta']}, "
                 f"t={e3['rank1_falsification']['t']}, within-R2="
                 f"{e3['rank1_falsification']['within_r2']}\n\n")
        fh.write("## E3b. Subdomain horse race on AI-demand growth 2020-2023\n")
        fh.write(f"- n={e3b['n']} occupations (min 100 ads); outcome: change in ads "
                 f"AI-share, percentage points; regressors standardised\n")
        fh.write(f"- genai exposure growth: beta={e3b['beta_genai_pp_per_sd']} pp/sd, "
                 f"t={e3b['t_genai']}\n")
        fh.write(f"- image-recognition exposure growth: beta={e3b['beta_imgrec_pp_per_sd']} "
                 f"pp/sd, t={e3b['t_imgrec']}\n")
        fh.write(f"- Spearman with the outcome: {e3b['spearman']}\n")
    print(rep.read_text())


if __name__ == "__main__":
    main()
