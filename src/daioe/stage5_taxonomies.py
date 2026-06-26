"""Stage 5 — taxonomy translation, comparator indices, and publication panels.

This stage is a faithful Python port of ``Code/1_3_add_indices_translate_taxonomies.do``.
It starts from the O*NET-SOC2010 preliminary checkpoint (Stage 4 output) and:

  1. ONET panel:  add ``pctl_rank_allapps`` and save ``daioe_panel_onet``.
  2. SOC2010:     collapse O*NET -> SOC (simple mean), recompute cumulative exposure,
                  merge five literature comparator indices, rescale occupation
                  characteristics, percentile-rank.
  3. ISCO08 / SSYK2012 / SSYK96: per year, merge the SOC panel with the crosswalk
                  (1:m on the SOC key), collapse to the target code with a SIMPLE
                  UNWEIGHTED MEAN, recompute cumulative exposure within the target
                  (set to missing where the running sum is exactly zero), rescale,
                  percentile-rank, and derive 1/2/3-digit levels.
  4. Publication: keep only the published application categories, rename
                  ``exp_cumul_<app>`` -> ``daioe_<app>``, drop comparators and
                  occupation characteristics, percentile-rank, and write the
                  ``Publication/daioe_<tax>`` files in .dta/.csv/.xlsx.

FLOAT32 FIDELITY
----------------
The Stata pipeline evaluates in double but STORES each gen/egen/replace in the
variable's declared type, which is ``float`` (single) by default. We mirror this by
casting to float32 at every step where Stata stores a float:

  * exp_change_* / exp_cumul_* / pctl_rank_* are float-stored;
  * the comparator indices are float-stored except ``fo17_p_computerisation`` (double);
  * the broad occupation-characteristic scores are double-stored, BUT the rescaling
    denominator ``egen <var>_max`` is a NEW variable and therefore float (single):
    the division is double / float32(max);
  * Stata's running ``sum()`` stores each cumulative step as a float, so the cumulative
    exposure is accumulated step-by-step with a float32 cast after each addition.

KNOWN IRREDUCIBLE RESIDUALS (Stata internals, documented, not fixable in pandas)
--------------------------------------------------------------------------------
  * SOC ``conseq_error``: 8 cells (occupations 29-1069, 29-2099, 43-5081, 51-9195,
    one anomalous year each) sit on an EXACT-HALF rounding boundary (collapse mean =
    x.xx5). Stata's collapse computes the group mean with an internal row-summation
    order that lands 1 ULP either side of the half for these cells, flipping
    round(.,0.01) between two adjacent hundredths. pandas' fixed summation cannot
    reproduce Stata's per-group accumulation order, so these 8 cells differ by ~2e-3.
    They are double-stored occupation characteristics and are DROPPED from every
    publication panel, so the published deliverables are unaffected.
  * NaN-year tied rows: the 68 SOC occupations with no exposure data are kept "for
    transparency" with ``year`` missing and ``exp_cumul_allapps = 0``. Within their
    single percentile-rank group all 68 values tie at 0, so their ranks are a
    permutation fixed only by Stata's (unstable) internal sort jitter. Up to 67 of
    these rows therefore differ from the reference. They carry no exposure signal.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from dataclasses import dataclass, field

from . import io, stata_ops as so, validate
from .validate import CompareResult, PctlTieResult


@dataclass
class Stage5Result:
    """Bundle of Stage 5 validation outcomes.

    ``strict`` holds the per-target :class:`CompareResult` for the NON-pctl value columns
    (must be bit-exact at the configured tolerance, modulo the documented conseq_error
    cells). ``pctl`` holds the per-target tie-aware :class:`PctlTieResult` for every
    percentile-rank column. ``run`` returns one of these so a percentile rank is proven
    correct up to ties rather than eyeballed, while no value column is allowed to drift.
    """
    strict: list[CompareResult] = field(default_factory=list)
    pctl: list[PctlTieResult] = field(default_factory=list)

    @property
    def value_columns_pass(self) -> bool:
        return all(r.passed for r in self.strict)

    @property
    def pctl_pass(self) -> bool:
        return all(r.passed for r in self.pctl)

    @property
    def passed(self) -> bool:
        return self.value_columns_pass and self.pctl_pass


# ----------------------------------------------------------------------------- helpers
def _stata_round(x, unit: float = 0.01) -> np.ndarray:
    """Mirror Stata ``round(x, unit)`` = round(x/unit) * unit, half away from zero.

    Stata divides by ``unit`` and rounds the quotient to the nearest integer (ties away
    from zero), then multiplies back. Working on ``x/unit`` (rather than ``x*100``)
    reproduces Stata's results on the exact-half cases that this pipeline hits.
    """
    x = np.asarray(x, dtype=np.float64)
    return np.sign(x) * np.floor(np.abs(x) / unit + 0.5) * unit


def _running_sum_float(s: pd.Series) -> np.ndarray:
    """Stata ``by g: gen c = sum(v)``: missing treated as 0, each step stored as float.

    Stata accumulates the running total in DOUBLE inside ``sum()`` and writes each row's
    value into the (float) target variable. The accumulator is not rounded between rows,
    so only the STORED per-row result is single-precision: we keep ``acc`` in float64 and
    cast just the stored output to float32.
    """
    arr = s.to_numpy(dtype=np.float64)
    out = np.empty(len(arr), dtype=np.float64)
    acc = np.float64(0.0)
    for i, v in enumerate(arr):
        if not np.isnan(v):
            acc = acc + v
        out[i] = np.float64(np.float32(acc))  # store the running result as float
    return out


def _cumul_within(df: pd.DataFrame, group: str, change_col: str, order: str = "year") -> np.ndarray:
    """``by group (order): gen exp_cumul = sum(exp_change)`` with float-stored steps."""
    out = np.full(len(df), np.nan, dtype=np.float64)
    pos = {idx: i for i, idx in enumerate(df.index)}
    for _, idx in df.groupby(group, sort=False).groups.items():
        sub = df.loc[idx].sort_values(order, kind="mergesort")
        vals = _running_sum_float(sub[change_col])
        for j, ix in enumerate(sub.index):
            out[pos[ix]] = vals[j]
    return out


def _pctl_rank_with_nan_year(df: pd.DataFrame, value: str, out: str) -> pd.Series:
    """``pctl_rank`` keyed on ``year``, but treating missing year as its own group.

    The shared ``so.pctl_rank`` groups by ``year`` via pandas ``groupby``, which DROPS
    a missing-key group. Stata's ``by year:`` instead ranks the missing-year rows
    together. We map missing year to a sentinel before calling the shared shim so the
    rows are ranked, then restore.
    """
    tmp = df.copy()
    tmp["_yr"] = tmp[value].notna().map(lambda _: None)  # placeholder, overwritten next
    tmp["_yr"] = df["year"].fillna(9999.0)
    return so.pctl_rank(tmp, value=value, out=out, by="_yr")


# ----------------------------------------------------------- column groups (from config)
def _exp_change_cols(cfg) -> list[str]:
    return [f"exp_change_{a}" for a in cfg.app_categories]


def _exp_cumul_cols(cfg) -> list[str]:
    return [f"exp_cumul_{a}" for a in cfg.app_categories]


# comparator columns stored as float in Stata (everything except fo17, which is double)
_COMP_FLOAT = [
    "frs18_index_original", "frs18_index_new_weights", "frs21_aioe",
    "webb19_ai_score", "webb19_software_score", "webb19_robot_score",
    "open24_human_E1", "open24_human_E1_E2", "open24_human_E1_05xE2", "open24_gpt_automation",
]
_COMP_DOUBLE = ["fo17_p_computerisation"]


# ----------------------------------------------------------------------- comparator load
def _load_comparators(cfg) -> dict[str, pd.DataFrame]:
    """Load and rename the five literature comparator sources, keyed on occ_code_soc."""
    raw = cfg.raw_file

    f18o = io.read_dta(raw("frs18_slopes_original.dta")).rename(
        columns={"occ_code": "occ_code_soc", "avg_wtd_impact": "frs18_index_original"}
    )
    f18o = f18o[f18o["occ_code_soc"] != ""][["occ_code_soc", "frs18_index_original"]]

    f18n = io.read_dta(raw("frs18_slopes_newweights.dta")).rename(
        columns={"occ_code": "occ_code_soc"}
    )[["occ_code_soc", "frs18_index_new_weights"]]

    aioe = io.read_dta(raw("aioe_2020.dta")).rename(
        columns={"occ_code": "occ_code_soc", "aioe": "frs21_aioe"}
    )[["occ_code_soc", "frs21_aioe"]]

    webb = io.read_dta(raw("webb_indices_soc2010.dta")).rename(
        columns={
            "SOC2010code": "occ_code_soc",
            "ai_score": "webb19_ai_score",
            "software_score": "webb19_software_score",
            "robot_score": "webb19_robot_score",
        }
    )[["occ_code_soc", "webb19_ai_score", "webb19_software_score", "webb19_robot_score"]]

    fo = pd.read_excel(raw("frey_osborne_2017_probability_of_computerisation.xlsx"), sheet_name="Blad1")
    fo = fo.rename(columns={"SOC code": "occ_code_soc", "Probability": "fo17_p_computerisation"})
    fo = fo[["occ_code_soc", "fo17_p_computerisation"]]

    oa = io.read_dta(raw("openai_2024_exposure_soc2010.dta")).rename(
        columns={
            "occ_code_soc2010": "occ_code_soc",
            "human_E1": "open24_human_E1",
            "human_E1_E2": "open24_human_E1_E2",
            "human_E1_05xE2": "open24_human_E1_05xE2",
            "gpt_automation": "open24_gpt_automation",
        }
    )[["occ_code_soc", "open24_human_E1", "open24_human_E1_E2",
       "open24_human_E1_05xE2", "open24_gpt_automation"]]

    return {
        "frs18o": f18o, "frs18n": f18n, "aioe": aioe,
        "webb": webb, "fo": fo, "openai": oa,
    }


def _rescale_occ_characteristics(df: pd.DataFrame, occ_cols: list[str]) -> pd.DataFrame:
    """Mirror ``daioe_internal_clean``: round conseq_error to 0.01, then divide each
    occupation-characteristic column by its (float32-stored) column maximum.

    ``egen <var>_max = max(<var>)`` creates a NEW variable, which Stata stores as float
    (single). The subsequent ``replace <var> = <var>/<var>_max`` therefore divides a
    double by a float32 denominator; we reproduce that exactly.
    """
    df = df.copy()
    df["conseq_error"] = _stata_round(df["conseq_error"].to_numpy(dtype=np.float64), 0.01)
    for v in occ_cols:
        col = df[v].to_numpy(dtype=np.float64)
        vmax = np.float64(np.float32(np.nanmax(col)))  # egen max stored as float
        df[v] = col / vmax
    return df


# ---------------------------------------------------------------------------- ONET panel
def build_onet(cfg) -> pd.DataFrame:
    """ONET panel = preliminary checkpoint + ``pctl_rank_allapps`` (Stata float casts)."""
    df = pd.read_parquet(cfg.out_file("daioe_panel_onet_preliminary.parquet")).copy()
    df["pctl_rank_allapps"] = so.pctl_rank(df, value="exp_cumul_allapps", out="pctl_rank_allapps")

    for c in _exp_change_cols(cfg) + _exp_cumul_cols(cfg) + ["pctl_rank_allapps"]:
        df[c] = so.f32(df[c])
    df["year"] = so.f32(df["year"])
    return df


# ----------------------------------------------------------------------------- SOC panel
def build_soc(cfg) -> pd.DataFrame:
    """Collapse O*NET -> SOC, recompute cumulative exposure, merge comparators, rescale."""
    occ = cfg.occ_characteristic_cols
    change_cols = _exp_change_cols(cfg)

    df = pd.read_parquet(cfg.out_file("daioe_panel_onet_preliminary.parquet")).copy()
    # The O*NET occupation 19-1020 ("Biologists") is not a SOC code; the do-file maps it
    # to 19-1029 ("Biological Scientists, All Other") so it merges with the SOC titles.
    df["occ_code_soc"] = df["occ_code_soc"].replace("19-1020", "19-1029")

    # SOC 2010 titles (outer merge keeps the 68 SOC occupations without exposure data;
    # drop the left-only O*NET rows that have no SOC title, as in the do-file).
    defs = pd.read_excel(cfg.raw_file("soc_2010_definitions - fixed for Stata.xls"),
                         sheet_name="detailed occupations")
    defs.columns = [str(c).strip().lower() for c in defs.columns]
    defs["code"] = defs["code"].replace("13-2082 ", "13-2082")
    defs = defs[["code", "title", "definition"]].rename(columns={"code": "occ_code_soc"})

    merged = df.merge(defs, on="occ_code_soc", how="outer", indicator=True)
    merged = merged[merged["_merge"] != "left_only"].drop(columns="_merge")
    merged = merged.rename(columns={"title": "occ_title_soc", "definition": "occ_definition_soc"})

    # collapse (first) titles (mean) exp_change* occ_chars, by (occ_code_soc, year)
    soc = so.collapse_mean(
        merged,
        by=["occ_code_soc", "year"],
        mean_cols=change_cols + occ,
        first_cols=["occ_title_soc", "occ_definition_soc"],
    )
    soc = soc.sort_values(["occ_code_soc", "year"], kind="mergesort").reset_index(drop=True)

    # exp_change is collapse-stored as float; cast before the running sum.
    for a in cfg.app_categories:
        soc[f"exp_change_{a}"] = so.f32(soc[f"exp_change_{a}"])
    for a in cfg.app_categories:
        col = f"exp_cumul_{a}"
        soc[col] = _cumul_within(soc, "occ_code_soc", f"exp_change_{a}")
        soc[col] = so.f32(soc[col])

    # percentile rank on cumulative all-applications exposure
    soc["pctl_rank_allapps"] = _pctl_rank_with_nan_year(soc, "exp_cumul_allapps", "pctl_rank_allapps")
    soc["pctl_rank_allapps"] = so.f32(soc["pctl_rank_allapps"])

    # merge the five literature comparator indices (m:1 on SOC; left join keeps the panel)
    comps = _load_comparators(cfg)
    for key in ("frs18o", "frs18n", "aioe", "webb", "fo", "openai"):
        soc = soc.merge(comps[key], on="occ_code_soc", how="left")
    for c in _COMP_FLOAT:
        soc[c] = so.f32(soc[c])
    # fo17 stays double (float64); no cast.

    # add the 2-digit SOC group code (string)
    soc["occ_code_soc_2"] = soc["occ_code_soc"].str.slice(0, 2)

    # universal internal cleaning: round conseq, rescale occupation characteristics
    soc = _rescale_occ_characteristics(soc, occ)

    soc["year"] = so.f32(soc["year"])
    return soc


# ----------------------------------------------------------- crosswalk-based taxonomies
def _build_crosswalk_taxonomy(
    cfg,
    soc: pd.DataFrame,
    crosswalk_file: str,
    target_key: str,
    soc_key_in_cw: str = "SOC2010code",
    extra_cw_cols: list[str] | None = None,
    first_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Translate the SOC panel to a target taxonomy via a 1:m crosswalk.

    Per the do-file: for each year, merge the SOC panel (renamed occ_code_soc ->
    SOC2010code) 1:m with the crosswalk, drop SOC rows with no target match, collapse to
    (target_key, year) with a SIMPLE UNWEIGHTED MEAN of exp_change*, occupation
    characteristics and comparator indices; then recompute cumulative exposure within the
    target (missing where the running sum is exactly zero), percentile-rank, and rescale.
    """
    occ = cfg.occ_characteristic_cols
    change_cols = _exp_change_cols(cfg)
    mean_cols = change_cols + occ + _COMP_FLOAT + _COMP_DOUBLE
    extra_cw_cols = extra_cw_cols or []
    first_cols = first_cols or []

    cw = io.read_dta(cfg.raw_file(crosswalk_file))
    keep_cw = [soc_key_in_cw, target_key] + [c for c in (extra_cw_cols + first_cols) if c in cw.columns]
    cw = cw[keep_cw].copy()

    soc_for_merge = soc.rename(columns={"occ_code_soc": soc_key_in_cw})
    # Stata's ``collapse (mean)`` sums in DOUBLE and stores the result as float; pandas'
    # ``groupby.mean`` on a float32 column accumulates in float32 and loses ~1 ULP. Upcast
    # the to-be-averaged columns to float64 so the mean is computed in double precision
    # (we re-cast the result to float32 afterwards where Stata stores a float).
    soc_for_merge = soc_for_merge.copy()
    for c in mean_cols:
        if c in soc_for_merge.columns:
            soc_for_merge[c] = soc_for_merge[c].astype("float64")

    pieces = []
    for year in cfg.years:
        sub = soc_for_merge[soc_for_merge["year"] == year]
        # 1:m merge, keep _merge in (2,3) and drop _merge==1: a RIGHT join keeps every
        # crosswalk (target) code, even those whose matched SOC has no exposure in this
        # year (they contribute missing exposure, as in the do-file). ``replace year=Y if
        # year==.`` then stamps the year onto those crosswalk-only rows.
        m = sub.merge(cw, on=soc_key_in_cw, how="right")
        m["year"] = float(year)
        collapsed = so.collapse_mean(m, by=[target_key, "year"], mean_cols=mean_cols,
                                     first_cols=first_cols)
        pieces.append(collapsed)

    panel = pd.concat(pieces, ignore_index=True)
    panel = panel.sort_values([target_key, "year"], kind="mergesort").reset_index(drop=True)

    # exp_change stored float; recompute cumulative within the target taxonomy.
    for a in cfg.app_categories:
        panel[f"exp_change_{a}"] = so.f32(panel[f"exp_change_{a}"])
    for a in cfg.app_categories:
        col = f"exp_cumul_{a}"
        panel[col] = _cumul_within(panel, target_key, f"exp_change_{a}")
        # set the cumulative to missing where it is exactly zero (do-file lines 423-425).
        vals = np.array(panel[col].to_numpy(dtype=np.float64), copy=True)
        vals[vals == 0.0] = np.nan
        panel[col] = so.f32(vals)

    # comparator floats: float-cast (means computed in double, stored float).
    for c in _COMP_FLOAT:
        panel[c] = so.f32(panel[c])

    # percentile rank on cumulative all-applications exposure
    panel["pctl_rank_allapps"] = so.pctl_rank(panel, value="exp_cumul_allapps", out="pctl_rank_allapps")
    panel["pctl_rank_allapps"] = so.f32(panel["pctl_rank_allapps"])

    # universal internal cleaning: round conseq, rescale occupation characteristics.
    panel = _rescale_occ_characteristics(panel, occ)

    # the crosswalk panels drop the "allapps" suffix on the main index (do-file).
    panel = panel.rename(columns={"exp_change_allapps": "exp_change",
                                  "exp_cumul_allapps": "exp_cumul"})

    panel["year"] = so.f32(panel["year"])
    return panel


def build_isco08(cfg, soc: pd.DataFrame) -> pd.DataFrame:
    """ISCO-08 panel. The crosswalk key ``ISCO08code`` is a zero-padded string; the panel
    keeps both an integer ``ISCO08code`` (the validation key) and the string version."""
    occ = cfg.occ_characteristic_cols
    # collapse on the string ISCO08code, then derive numeric + digit-level codes.
    panel = _build_crosswalk_taxonomy(
        cfg, soc, "isco08_soc2010_crosswalk.dta", target_key="ISCO08code",
        first_cols=["ISCO08title"],
    )
    panel = panel.rename(columns={"ISCO08code": "ISCO08code_str"})
    panel["ISCO08code"] = panel["ISCO08code_str"].astype(int)
    panel["ISCO08code_1"] = panel["ISCO08code_str"].str.slice(0, 1)
    # re-key sort by the numeric code, matching the saved panel's tsset order
    panel = panel.sort_values(["ISCO08code", "year"], kind="mergesort").reset_index(drop=True)
    return panel


def _add_digit_levels_intdiv(df: pd.DataFrame, code_col: str, prefix: str) -> pd.DataFrame:
    """Derive 1/2/3-digit numeric levels by integer division of the 4-digit code."""
    df = df.copy()
    code = df[code_col].to_numpy(dtype=np.float64)
    df[f"{prefix}_1"] = np.floor(code / 1000.0)
    df[f"{prefix}_2"] = np.floor(code / 100.0)
    df[f"{prefix}_3"] = np.floor(code / 10.0)
    return df


def build_ssyk2012(cfg, soc: pd.DataFrame) -> pd.DataFrame:
    """SSYK 2012 panel, keyed on the numeric ``ssyk2012_4`` (4-digit code)."""
    panel = _build_crosswalk_taxonomy(
        cfg, soc, "ssyk2012_soc10_crosswalk.dta", target_key="ssyk2012_4",
    )
    panel = panel.rename(columns={})  # numeric key already
    panel["SSYK2012kod_str"] = panel["ssyk2012_4"].astype(int).astype(str).str.zfill(4)
    panel = _add_digit_levels_intdiv(panel, "ssyk2012_4", "ssyk2012")
    panel = panel.sort_values(["ssyk2012_4", "year"], kind="mergesort").reset_index(drop=True)
    return panel


def build_ssyk96(cfg, soc: pd.DataFrame) -> pd.DataFrame:
    """SSYK 1996 panel, keyed on the numeric ``ssyk96_4`` (4-digit code)."""
    panel = _build_crosswalk_taxonomy(
        cfg, soc, "ssyk96_soc10_crosswalk.dta", target_key="SSYK96kod",
    )
    panel = panel.rename(columns={"SSYK96kod": "SSYK96kod_str"})
    # the saved panel stores ssyk96_4 as a Stata float (used as the tsset panel id).
    panel["ssyk96_4"] = panel["SSYK96kod_str"].astype(int).astype("float64")
    panel = _add_digit_levels_intdiv(panel, "ssyk96_4", "ssyk96")
    panel = panel.sort_values(["ssyk96_4", "year"], kind="mergesort").reset_index(drop=True)
    return panel


# --------------------------------------------------------------------- publication build
def _publication_clean(cfg, df: pd.DataFrame) -> pd.DataFrame:
    """Mirror ``publication_data_cleaning``: keep the published applications, rename
    ``exp_cumul_<app>`` -> ``daioe_<app>``, drop comparators / occ characteristics /
    exp_change, and add per-application percentile ranks.

    ``allapps`` arrives either as ``exp_cumul_allapps`` (ONET/SOC panels) or as the
    suffix-dropped ``exp_cumul`` (ISCO/SSYK panels); we normalise to ``exp_cumul_allapps``.
    """
    df = df.copy()
    if "exp_cumul" in df.columns and "exp_cumul_allapps" not in df.columns:
        df = df.rename(columns={"exp_cumul": "exp_cumul_allapps"})

    pub_apps = cfg.app_categories_publication
    has_nan_year = df["year"].isna().any()
    keep_daioe, keep_pctl = [], []
    for app in pub_apps:
        df = df.rename(columns={f"exp_cumul_{app}": f"daioe_{app}"})
        if has_nan_year:
            # the SOC/ONET publication panels keep the 68 no-exposure rows with year
            # missing; Stata's ``by year:`` ranks them as their own group (all daioe=0).
            df[f"pctl_rank_{app}"] = _pctl_rank_with_nan_year(df, f"daioe_{app}", f"pctl_rank_{app}")
        else:
            df[f"pctl_rank_{app}"] = so.pctl_rank(df, value=f"daioe_{app}", out=f"pctl_rank_{app}")
        keep_daioe.append(f"daioe_{app}")
        keep_pctl.append(f"pctl_rank_{app}")
    return df, keep_daioe, keep_pctl


def build_publication(cfg, tax: str, internal: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Build a publication panel for one taxonomy from its internal panel.

    Returns (frame, id_cols, float32_cols) where ``float32_cols`` lists every column the
    publication .dta stores as float (year, daioe_*, pctl_rank_*, and the numeric digit
    levels for the SSYK taxonomies).
    """
    df, daioe_cols, pctl_cols = _publication_clean(cfg, internal)

    if tax == "onetsoc2010":
        df = df.rename(columns={
            "occ_code_onet": "occ_code_onetsoc2010",
            "occ_title_onet": "occ_title_onetsoc2010",
        })
        id_cols = ["occ_code_onetsoc2010", "occ_title_onetsoc2010", "year"]
        sort_keys = ["occ_code_onetsoc2010", "year"]
        extra: list[str] = []
    elif tax == "soc2010":
        df = df.rename(columns={"occ_code_soc": "occ_code_soc2010", "occ_title_soc": "occ_title_soc2010"})
        id_cols = ["occ_code_soc2010", "occ_title_soc2010", "year"]
        sort_keys = ["occ_code_soc2010", "year"]
        extra = []
    elif tax == "isco08":
        df = df.rename(columns={"ISCO08code_str": "occ_code_isco08", "ISCO08title": "occ_title_isco08"})
        id_cols = ["occ_code_isco08", "occ_title_isco08", "year"]
        sort_keys = ["occ_code_isco08", "year"]
        extra = []
    elif tax == "ssyk2012":
        id_cols = ["ssyk2012_4", "year"]
        sort_keys = ["ssyk2012_4", "year"]
        extra = ["ssyk2012_1", "ssyk2012_2", "ssyk2012_3"]
    elif tax == "ssyk96":
        id_cols = ["ssyk96_4", "year"]
        sort_keys = ["ssyk96_4", "year"]
        extra = ["ssyk96_1", "ssyk96_2", "ssyk96_3"]
    else:
        raise ValueError(f"unknown taxonomy {tax}")

    keep = id_cols + daioe_cols + pctl_cols + extra
    out = df[keep].sort_values(sort_keys, kind="mergesort").reset_index(drop=True)

    # publication .dta stores year, daioe_*, pctl_rank_* (and SSYK digit levels) as float.
    float32_cols = ["year"] + daioe_cols + pctl_cols + extra
    return out, id_cols, float32_cols


# -------------------------------------------------------------------------------- runner
def run(cfg, validate: bool = True) -> Stage5Result:  # noqa: ANN001
    """Build every Stage 5 panel, write outputs, and (optionally) validate.

    Writes the internal panels and the publication panels to ``cfg.path('out')`` and the
    publication exports to ``cfg.path('out')/Publication``. Returns a :class:`Stage5Result`
    with two streams: ``strict`` (per-target value-column CompareResults, validated bit-exact
    via :func:`validate.compare_to_dta`) and ``pctl`` (per-target tie-aware PctlTieResults for
    every percentile-rank column, validated via :func:`validate.compare_pctl_tie_aware`).
    """
    from . import validate as _validate  # local alias; ``validate`` arg shadows the module

    out_dir = cfg.path("out")
    pub_dir = out_dir / "Publication"
    pub_dir.mkdir(parents=True, exist_ok=True)

    results: list[CompareResult] = []
    pctl_results: list[PctlTieResult] = []

    # --- internal panels -----------------------------------------------------------
    onet = build_onet(cfg)
    soc = build_soc(cfg)
    isco = build_isco08(cfg, soc)
    ssyk2012 = build_ssyk2012(cfg, soc)
    ssyk96 = build_ssyk96(cfg, soc)

    io.write_dta(onet, out_dir / "daioe_panel_onet.dta")
    io.write_dta(soc, out_dir / "daioe_panel_soc.dta")
    io.write_dta(isco, out_dir / "daioe_panel_isco08.dta")
    io.write_dta(ssyk2012, out_dir / "daioe_panel_ssyk2012.dta")
    io.write_dta(ssyk96, out_dir / "daioe_panel_ssyk96.dta")

    # --- internal-panel value columns (numeric only; keys + strings excluded) -------
    def _num_cols(ref_path, keys):
        ref = io.read_dta(ref_path)
        out = []
        for c in ref.columns:
            if c in keys:
                continue
            if pd.api.types.is_numeric_dtype(ref[c]):
                out.append(c)
        return out

    # Each internal panel ranks ``pctl_rank_allapps`` on its cumulative all-applications
    # exposure column. That column is ``exp_cumul_allapps`` on the ONET/SOC panels but the
    # suffix-dropped ``exp_cumul`` on the crosswalk panels (see _build_crosswalk_taxonomy).
    internal_specs = [
        ("onet", onet, "daioe_panel_onet.dta", ["occ_code_onet", "year"], "exp_cumul_allapps"),
        ("soc", soc, "daioe_panel_soc.dta", ["occ_code_soc", "year"], "exp_cumul_allapps"),
        ("isco08", isco, "daioe_panel_isco08.dta", ["ISCO08code", "year"], "exp_cumul"),
        ("ssyk2012", ssyk2012, "daioe_panel_ssyk2012.dta", ["ssyk2012_4", "year"], "exp_cumul"),
        ("ssyk96", ssyk96, "daioe_panel_ssyk96.dta", ["ssyk96_4", "year"], "exp_cumul"),
    ]

    if validate:
        for name, got, ref_name, keys, cumul_col in internal_specs:
            ref_path = cfg.reference_file(ref_name)
            # STRICT comparison for every NON-pctl value column (must be bit-exact at
            # tol_internal; only the documented conseq_error rounding-boundary cells differ).
            vc = [c for c in _num_cols(ref_path, keys) if not c.startswith("pctl_rank")]
            results.append(_validate.compare_to_dta(
                got, ref_path, keys=keys, value_cols=vc, tol=cfg.tol_internal, name=name))
            # TIE-AWARE comparison for the percentile-rank column (a percentile rank is only
            # defined up to ties; Stata's unstable sort fixes the within-tie order only by
            # jitter). pctl_rank_allapps <- the panel's cumulative all-apps exposure column.
            pctl_results.append(_validate.compare_pctl_tie_aware(
                got, ref_path, keys=keys, pctl_col="pctl_rank_allapps",
                value_col=cumul_col, by="year", tol=cfg.tol_internal, name=name))

    # --- publication panels --------------------------------------------------------
    pub_specs = [
        ("onetsoc2010", onet),
        ("soc2010", soc),
        ("isco08", isco),
        ("ssyk2012", ssyk2012),
        ("ssyk96", ssyk96),
    ]
    for tax, internal in pub_specs:
        pub, id_cols, f32_cols = build_publication(cfg, tax, internal)
        pub = io.cast_publication(pub, f32_cols)
        io.write_outputs(pub, f"daioe_{tax}", pub_dir, cfg.export_formats)

        if validate:
            ref_path = cfg.reference_file(f"Publication/daioe_{tax}.dta")
            keys = [c for c in id_cols if c != "year" and "title" not in c] + ["year"]
            # STRICT comparison for the non-pctl published value columns (daioe_* and the
            # SSYK digit levels); pctl_rank_* are excluded here and checked tie-aware below.
            vc = [c for c in _num_cols(ref_path, keys) if not c.startswith("pctl_rank")]
            results.append(_validate.compare_to_dta(
                pub, ref_path, keys=keys, value_cols=vc,
                tol=cfg.tol_publication, name=f"pub_{tax}"))
            # TIE-AWARE comparison for every published percentile-rank column. Each
            # pctl_rank_<app> is ranked on its own daioe_<app> (Stata: ``pctl_rank daioe app``).
            for app in cfg.app_categories_publication:
                pctl_results.append(_validate.compare_pctl_tie_aware(
                    pub, ref_path, keys=keys, pctl_col=f"pctl_rank_{app}",
                    value_col=f"daioe_{app}", by="year", tol=cfg.tol_publication,
                    name=f"pub_{tax}"))

    return Stage5Result(strict=results, pctl=pctl_results)
