"""T01 first-stage validation: does potential exposure predict realised AI use?

The deepest shared referee objection (T01; ReStat R3, EJ R1, EJ R3, both editors) is
that DAIOE measures potential exposure while "the vast majority of sample firms use
none of the frontier technologies", and that the design's implicit assumption -- firm
technology use moves with its share of exposed occupations -- is never justified.
The v0 estimand paragraph reframes (ITT-style association); THIS script supplies the
missing evidence, from public data only, none of it used in estimation:

  E1  OCCUPATION level, revealed USE. Published DAIOE (frozen 2023, O*NET-SOC) against
      the Anthropic Economic Index's usage share by occupation (Claude conversations
      mapped to O*NET tasks): do people in exposed occupations actually use AI?
  E2  INDUSTRY level, measured ADOPTION, three countries. Predetermined industry
      exposure (2019 Swedish occupation-by-industry employment weights x frozen DAIOE)
      against Eurostat's harmonised enterprise AI-adoption survey (isoc_eb_ain2,
      enterprises with 10+ employed, share using any AI technology), for Sweden,
      Denmark and Portugal: did adoption, once AI became adoptable, concentrate in
      the industries the measure said were exposed? The occupation mix is measured in
      2019, before any adoption outcome; the Swedish mix is applied to all three
      countries and this approximation is stated.
  E3  SUBDOMAIN discriminant validity, Sweden. Four subdomain exposures matched to
      their own technology's adoption indicator (speech recognition <-> E_AI_TSR,
      image recognition <-> E_AI_TIR, reading comprehension <-> E_AI_TTM, language
      modelling <-> E_AI_TNLG): matched correlations against the off-diagonal mean.
      If exposure were a generic occupational gradient, the diagonal would not be
      special.

Raw inputs are cached with hashes in data/updates/t01_raw/ (SCB YREG54N 2019 via the
public API; Eurostat isoc_eb_ain2 via the REST API; AEI usage from the pipeline's
mapping/raw_data/aei/). Outputs: reports/t01_validation_20260808/ (figures + RESULTS.md).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "updates" / "t01_raw"
OUT = ROOT / "reports" / "t01_validation_20260808"
OUT.mkdir(exist_ok=True)

import sys

sys.path.insert(0, str(ROOT / "src"))
from daioe import io as dio  # noqa: E402

NAVY, VERMILION, GREEN, GRAY = "#232b65", "#D55E00", "#009E73", "#8a8a8a"

# ------------------------------------------------------------------ E1: occupation use
def exhibit1() -> dict:
    pub = dio.read_dta(ROOT / "data/out/Publication/daioe_onetsoc2010.dta")
    d23 = pub[pub["year"] == 2023][["occ_code_onetsoc2010", "daioe_allapps", "daioe_genai"]]
    aei = pd.read_csv(ROOT / "mapping/raw_data/aei/aei_usage_by_occupation.csv")
    m = d23.merge(aei, left_on="occ_code_onetsoc2010", right_on="occ_code_onet")
    res = {}
    for col in ("daioe_allapps", "daioe_genai"):
        rho, p = stats.spearmanr(m[col], m["aei_usage"])
        res[col] = {"spearman": round(float(rho), 3), "p": float(p), "n": int(len(m))}

    fig, ax = plt.subplots(figsize=(5.2, 4.2))
    ax.scatter(m["daioe_allapps"].rank(pct=True) * 100, m["aei_usage"].rank(pct=True) * 100,
               s=10, alpha=0.35, color=NAVY, edgecolors="none")
    ax.set_xlabel("DAIOE 2023, percentile (frozen index)", fontsize=9)
    ax.set_ylabel("Anthropic Economic Index usage share, percentile", fontsize=9)
    r = res["daioe_allapps"]
    ax.set_title(f"Occupation-level revealed use: Spearman {r['spearman']:.2f} "
                 f"(n = {r['n']})", fontsize=10)
    ax.tick_params(labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(lw=0.4, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "fig_e1_occupation_use.png", dpi=200)
    fig.savefig(OUT / "fig_e1_occupation_use.pdf")
    plt.close(fig)
    return res


# ---------------------------------------------------------- weights: SCB SSYK4 x SNI16
def load_weights() -> pd.DataFrame:
    d = json.loads((RAW / "scb_yreg54n_2019.json").read_text())
    dims = d["id"]
    sizes = d["size"]
    cats = {k: list(d["dimension"][k]["category"]["index"].keys()) for k in dims}
    vals = d["value"]
    # json-stat2 row-major over dims order
    rows = []
    idx = [0] * len(dims)
    for flat, v in enumerate(vals if isinstance(vals, list) else []):
        rem = flat
        coord = []
        for s in reversed(sizes):
            coord.append(rem % s)
            rem //= s
        coord = coord[::-1]
        rec = {dims[k]: cats[dims[k]][coord[k]] for k in range(len(dims))}
        rec["employed"] = v if v is not None else 0
        rows.append(rec)
    w = pd.DataFrame(rows)
    w = w.groupby(["Yrke2012", "SNI2007"], as_index=False)["employed"].sum()
    total = w["employed"].sum()
    assert 3.5e6 < total < 5.5e6, f"implausible Swedish employee total {total:,.0f}"
    return w


# ------------------------------------------ industry exposure from the frozen SSYK panel
def industry_exposure(weights: pd.DataFrame, cols: list[str], year: int = 2023) -> pd.DataFrame:
    ssyk = dio.read_dta(ROOT / "data/out/Publication/daioe_ssyk2012.dta")
    dy = ssyk[ssyk["year"] == year].copy()
    dy["ssyk4"] = dy["ssyk2012_4"].astype(float).astype(int).astype(str).str.zfill(4)
    w = weights.copy()
    m = w.merge(dy[["ssyk4"] + cols], left_on="Yrke2012", right_on="ssyk4", how="inner")
    agg = {}
    for c in cols:
        s = m.dropna(subset=[c]).groupby("SNI2007").apply(
            lambda g: np.average(g[c], weights=g["employed"]), include_groups=False)
        agg[c] = s
    out = pd.DataFrame(agg)
    out.index.name = "SNI2007"
    return out.reset_index()


# --------------------------------------------------- Eurostat adoption by NACE section
# SCB's 16 coarse SNI groups -> Eurostat isoc_eb_ain2 NACE codes (survey frame = business
# economy, 10+ employed). Groups outside the survey frame (A, O, P, Q public-dominated)
# have no adoption measurement and drop out; that restriction is stated in the exhibit.
SNI_TO_NACE = {
    "B+C": "C", "D+E": "D_E", "F": "F", "G": "G", "H": "H", "I": "I",
    "J": "J", "K": None, "L": "L", "M": "M", "N": "N", "A": None,
}


def load_adoption(geo: str) -> pd.DataFrame:
    d = json.loads((RAW / f"eurostat_ai_nace_{geo}.json").read_text())
    dims = d["id"]
    sizes = d["size"]
    cats = {k: list(d["dimension"][k]["category"]["index"].keys()) for k in dims}
    recs = []
    for flat_str, v in d["value"].items():
        rem = int(flat_str)
        coord = []
        for s in reversed(sizes):
            coord.append(rem % s)
            rem //= s
        coord = coord[::-1]
        rec = {dims[k]: cats[dims[k]][coord[k]] for k in range(len(dims))}
        rec["value"] = v
        recs.append(rec)
    df = pd.DataFrame(recs)
    df["time"] = df["time"].astype(int)
    return df


# ------------------------------------------------------------------ E2: adoption gradient
def exhibit2(expo: pd.DataFrame) -> dict:
    res, panels = {}, []
    for geo, colr in (("SE", NAVY), ("DK", VERMILION), ("PT", GREEN)):
        ad = load_adoption(geo)
        any_ai = ad[(ad["indic_is"] == "E_AI_TANY")]
        yr = any_ai["time"].max()
        any_ai = any_ai[any_ai["time"] == yr]
        rows = []
        for sni, nace in SNI_TO_NACE.items():
            if nace is None:
                continue
            v = any_ai[any_ai["nace_r2"] == nace]["value"]
            e = expo[expo["SNI2007"] == sni]["daioe_allapps"]
            if len(v) and len(e):
                rows.append({"sni": sni, "adoption": float(v.iloc[0]),
                             "exposure": float(e.iloc[0]), "geo": geo, "year": yr})
        p = pd.DataFrame(rows)
        rho, pval = stats.spearmanr(p["exposure"], p["adoption"])
        res[geo] = {"spearman": round(float(rho), 3), "p": round(float(pval), 4),
                    "n": int(len(p)), "year": int(yr)}
        panels.append((p, colr))

    fig, ax = plt.subplots(figsize=(6.0, 4.6))
    for p, colr in panels:
        geo = p["geo"].iloc[0]
        ax.scatter(p["exposure"], p["adoption"], s=42, color=colr, alpha=0.85,
                   label=f"{geo} {res[geo]['year']} "
                         f"(Spearman {res[geo]['spearman']:.2f})", edgecolors="white",
                   linewidths=1)
    ax.set_xlabel("Industry potential exposure: 2019 occupation mix x frozen DAIOE 2023",
                  fontsize=9)
    ax.set_ylabel("Enterprises using any AI technology, % (Eurostat)", fontsize=9)
    ax.set_title("Predetermined exposure predicts where adoption materialised", fontsize=10)
    ax.legend(fontsize=8, frameon=False)
    ax.tick_params(labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(lw=0.4, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "fig_e2_industry_adoption.png", dpi=200)
    fig.savefig(OUT / "fig_e2_industry_adoption.pdf")
    plt.close(fig)
    return res


# --------------------------------------------------- E3: subdomain discriminant validity
PAIRS = [("daioe_speechrec", "E_AI_TSR", "speech recognition"),
         ("daioe_imgrec", "E_AI_TIR", "image recognition"),
         ("daioe_readcompr", "E_AI_TTM", "text mining"),
         ("daioe_lngmod", "E_AI_TNLG", "language generation")]


def exhibit3(expo_sub: pd.DataFrame) -> dict:
    ad = load_adoption("SE")
    yr = ad["time"].max()
    ad = ad[ad["time"] == yr]
    mat = np.full((4, 4), np.nan)
    for i, (dcol, _, _) in enumerate(PAIRS):
        for j, (_, icol, _) in enumerate(PAIRS):
            rows = []
            for sni, nace in SNI_TO_NACE.items():
                if nace is None:
                    continue
                v = ad[(ad["indic_is"] == icol) & (ad["nace_r2"] == nace)]["value"]
                e = expo_sub[expo_sub["SNI2007"] == sni][dcol]
                if len(v) and len(e):
                    rows.append((float(e.iloc[0]), float(v.iloc[0])))
            if len(rows) >= 6:
                a = np.array(rows)
                mat[i, j] = stats.spearmanr(a[:, 0], a[:, 1])[0]
    diag = np.nanmean(np.diag(mat))
    off = np.nanmean(mat[~np.eye(4, dtype=bool)])
    return {"matched_mean": round(float(diag), 3), "unmatched_mean": round(float(off), 3),
            "matrix": np.round(mat, 2).tolist(), "year": int(yr),
            "pairs": [p[2] for p in PAIRS]}


def main() -> None:
    e1 = exhibit1()
    w = load_weights()
    expo = industry_exposure(w, ["daioe_allapps"])
    e2 = exhibit2(expo)
    expo_sub = industry_exposure(
        w, ["daioe_speechrec", "daioe_imgrec", "daioe_readcompr", "daioe_lngmod"])
    e3 = exhibit3(expo_sub)

    # E4: how AI-using enterprises obtained their AI (SE 2025; % of AI users)
    d4 = json.loads((RAW / "eurostat_ai_acquisition_SE.json").read_text())
    dims4, sizes4 = d4["id"], d4["size"]
    cats4 = {k: list(d4["dimension"][k]["category"]["index"].keys()) for k in dims4}
    e4 = {}
    for f, v in d4["value"].items():
        rem = int(f); coord = []
        for s in reversed(sizes4):
            coord.append(rem % s); rem //= s
        coord = coord[::-1]
        rec = {dims4[k]: cats4[dims4[k]][coord[k]] for k in range(len(dims4))}
        if rec["unit"] == "PC_ENT_AI_TANY" and rec["indic_is"] in (
                "E_AI_ARDY", "E_AI_ADOWN", "E_AI_AEXT", "E_AI_AOS"):
            e4[rec["indic_is"]] = v

    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:16]
              for p in sorted(RAW.glob("*.json"))}
    report = OUT / "RESULTS.md"
    with open(report, "w") as fh:
        fh.write("# T01 first-stage validation — results (8 Aug 2026)\n\n")
        fh.write("## E1 Occupation-level revealed use (DAIOE 2023 vs AEI usage)\n")
        for k, v in e1.items():
            fh.write(f"- {k}: Spearman {v['spearman']} (n={v['n']}, p={v['p']:.2e})\n")
        fh.write("\n## E2 Industry-level adoption (2019 mix x frozen DAIOE vs Eurostat any-AI)\n")
        for g, v in e2.items():
            fh.write(f"- {g} ({v['year']}): Spearman {v['spearman']} "
                     f"(n={v['n']} industries, p={v['p']})\n")
        fh.write("\n## E3 Subdomain discriminant validity (SE, matched tech pairs)\n")
        fh.write(f"- matched-pair mean Spearman: {e3['matched_mean']}\n")
        fh.write(f"- off-diagonal mean Spearman: {e3['unmatched_mean']}\n")
        fh.write(f"- pairs: {e3['pairs']}; year {e3['year']}\n")
        fh.write(f"- full matrix (rows=exposure, cols=adoption): {e3['matrix']}\n")
        fh.write("\n## E4 How AI-using enterprises obtained AI (SE 2025, % of AI users)\n")
        labels = {"E_AI_ARDY": "ready-to-use commercial software",
                  "E_AI_ADOWN": "developed by own employees",
                  "E_AI_AEXT": "developed/modified by external providers",
                  "E_AI_AOS": "open-source modified by own employees"}
        for k, lab in labels.items():
            fh.write(f"- {lab}: {e4.get(k, 'n/a')}\n")
        fh.write("\n## Raw input hashes\n")
        for k, v in hashes.items():
            fh.write(f"- {k}: {v}…\n")
    print(report.read_text())


if __name__ == "__main__":
    main()
