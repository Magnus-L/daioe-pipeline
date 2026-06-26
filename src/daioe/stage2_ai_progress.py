"""Stage 2 - AI progress (Delta p_it), the only time-varying input to DAIOE.

This reproduces ``Code/1_1_AI_progress_data.do``. The economic object is the
*yearly rate of AI progress* in each AI application: how much closer the
state-of-the-art (SOTA) on each benchmark moved towards (or past) a meaningful
ceiling, per year, averaged across the benchmarks belonging to an application.

Pipeline (mirroring the do-file):

  1. Build the MEASURES panel: the new 2023 Papers-With-Code data (master)
     left-merged with the EFF/FRS18 ``measures.csv`` (using), keyed on
     (metrics_name, date, name, value). Clean the date strings.
  2. Build the METRICS panel: the new 2023 ``metrics`` sheet (master) merged
     1:1 with the EFF ``metrics.csv`` (using) on (metrics_name, parent_name).
     From it keep (axis_label, metrics_name, scale, target, target_label).
  3. Merge measures m:1 on metrics_name to attach the scale, then RESCALE each
     benchmark value according to its scale_type (the ~10 transforms in the
     do-file, lines 284-329). This turns exponential-decay error curves into
     roughly linear "progress" curves (Felten et al. 2018 approach).
  4. Build the SOTA frontier per metric (running max of value_scaled in date
     order); ``frontier`` flags an improvement.  -> formated_data.dta
  5. Collapse to (metrics_name, year); merge a full year skeleton; interpolate
     the gap years between SOTA jumps so a jump is spread evenly across the
     years since the previous jump (glapp / delta / deltanew / deltafinal).
     Then mean(deltafinal) per (parent_name, year) = Delta p_it. -> metrics_frontiers.dta
  6. Collapse to (parent_name, year); add a dummy "robotics" row; map EFF parent
     names to clean application names + application_id; filter by app-id
     membership to produce slopes_slimmed_<app> for all 13 categories.

The Stata code is authoritative; every non-obvious step is annotated with the
do-file line it mirrors.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import io, validate


# --------------------------------------------------------------------------- #
# Name maps (do-file lines 90-98 / 508-538).                                  #
# --------------------------------------------------------------------------- #

# EFF parent_name -> clean application name (do-file 508-520).
_APP_NAME = {
    "Accurate modelling of human language.": "language modeling",
    "Detection of Instrumentals musical tracks": "Detection of Instrumentals musical tracks",
    "Drawing pictures": "generating images",
    "Image classification": "image recognition",
    "Image comprehension": "visual question answering",
    "Language comprehension and question-answering": "reading comprehension",
    "Playing abstract games with extensive hints": "abstract strategy games",
    "Simple video games": "real-time video games",
    "Speech Recognition": "speech recognition",
    "Translation between human langauges": "translation",
    "Turing test for casual conversation": "conversation",
    "Write computer programs from specifications": "generating computer programs from specifications",
    "robotics": "robotics",
}

# clean application name -> application_id (do-file 526-538).
_APP_ID = {
    "Detection of Instrumentals musical tracks": 1,
    "abstract strategy games": 2,
    "conversation": 3,
    "generating computer programs from specifications": 4,
    "generating images": 5,
    "image recognition": 6,
    "language modeling": 7,
    "reading comprehension": 8,
    "real-time video games": 9,
    "speech recognition": 10,
    "translation": 11,
    "visual question answering": 12,
    "robotics": 18,
}

# app-category -> set of application_ids kept (do-file 541-579).
_CATEGORY_IDS = {
    "allapps": [2, 5, 6, 7, 8, 9, 10, 11, 12],
    "stratgames": [2],
    "videogames": [9],
    "imgrec": [6],
    "imgcompr": [12],
    "imggen": [5],
    "readcompr": [8],
    "lngmod": [7],
    "translat": [11],
    "speechrec": [10],
    "roe": [18],
    "genai": [5, 7],
    "redux": [2, 6, 8, 9, 10, 11, 12],
}

# The nine EFF parent names kept (do-file 90-98): only these survive the
# parent_name_cleaned step that filters the new-measures sheet membership.
_NINE_PARENTS = {
    "Accurate modelling of human language.",
    "Drawing pictures",
    "Image classification",
    "Image comprehension",
    "Language comprehension and question-answering",
    "Playing abstract games with extensive hints",
    "Simple video games",
    "Speech Recognition",
    "Translation between human langauges",
}

# metrics_name values that get target_label="Human performance" assigned
# (do-file 247-260). "Simple video games" is assigned by parent_name (246).
_HUMAN_PERF_METRICS = {
    "CIFAR-10 Image Recognition",
    "COCO Visual Question Answering (VQA) abstract images 1.0 open ended",
    "COCO Visual Question Answering (VQA) real images 1.0 open ended",
    "LAMBADA prediction of words in discourse",
    "MNIST handwritten digit recognition",
    "Precision of Instrumentals detection reached when tested on SATIN (Bayle et al. 2017)",
    "Stanford Question Answering Dataset EM test",
    "Stanford Question Answering Dataset F1 test",
    "Street View House Numbers (SVHN)",
    "Word error rate on Switchboard trained against the Hub5'00 dataset",
    "bAbi Children's Book comprehension CBtest CN",
    "librispeech WER testclean",
    "librispeech WER testother",
    "wsj WER eval92",
}


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _datestr(x) -> str:
    """Normalise an Excel date cell to 'YYYY-MM-DD' (do-file 159-173).

    The new-2023 sheet stores some dates as strings ('1984-12-31') and some as
    Excel datetimes. Stata cleans both to 'YYYY-MM-DD'. We keep string dates
    verbatim (they are already in that format) and format datetimes.
    """
    if isinstance(x, str):
        return x.strip()
    if pd.isna(x):
        return ""
    # pandas Timestamp / datetime
    return pd.Timestamp(x).strftime("%Y-%m-%d")


def _build_measures(cfg) -> pd.DataFrame:
    """Construct the merged MEASURES panel (do-file 144-176).

    New-2023 sheet is the *master* (1), EFF measures the *using* (m). The Stata
    merge is ``merge 1:m metrics_name date name value``, then ``drop if
    _merge==2``: keep matched rows (expanded by the m side) and unmatched-master
    rows. We carry parent_name/papername from the EFF side where matched, else
    from the new sheet (keepusing only pulls parent_name/papername, but for the
    matched rows the master already holds them; for unmatched-master rows the
    master values stand).
    """
    # --- new 2023 measures sheet (master) ---
    ms = io.read_excel_sheet(cfg.raw_file("measures_metrics_newdata2023.xlsx"), sheet="measures")
    new = ms[["parent_name", "metrics_name", "papername", "name", "date", "value"]].copy()
    # drop if metrics_name=="" (do-file 148)
    new = new[new["metrics_name"].notna() & (new["metrics_name"].astype(str).str.strip() != "")]
    # date as string key for the merge (Stata merges on the raw date string)
    new["date"] = new["date"].map(_datestr)
    # duplicates drop (do-file 149): full-row identical duplicates collapse
    new = new.drop_duplicates()
    new = new.reset_index(drop=True)

    # --- EFF measures (using, the "m" side) ---
    eff = pd.read_csv(cfg.raw_file("measures.csv"))
    eff = eff[["metrics_name", "date", "name", "value", "parent_name", "papername"]].copy()
    eff["date"] = eff["date"].astype(str).str.strip()

    # The merge key includes ``value``. Stata's ``import delimited`` stores the
    # EFF value as a single-precision float, and ``import excel`` stores the new
    # value as float too. So e.g. EFF "51.6" and new "51.599998" are the SAME
    # float32 bit pattern and DO match. We reproduce this by casting both value
    # columns to float32 and building a stable string key from it, so that the
    # merge matches exactly as Stata's does (this recovers the LAMBADA row that
    # is double-matched -> 2108 rows, not 2107).
    new["_vkey"] = new["value"].astype("float32").astype("float64")
    eff["_vkey"] = eff["value"].astype("float32").astype("float64")

    keys = ["metrics_name", "date", "name", "_vkey"]

    # Stata 1:m merge: master row may match several using rows -> expand.
    # We emulate with an indicator merge keeping both parent_name/papername
    # versions, then resolve so the matched rows take the EFF (using) values
    # for the kept columns (keepusing(parent_name papername) overwrites master
    # for _merge==3 because the master already had them identical; result is
    # the same value). drop if _merge==2.
    merged = new.merge(
        eff,
        on=keys,
        how="outer",
        suffixes=("_new", "_eff"),
        indicator=True,
    )
    # drop _merge==2 == "right_only" (EFF rows with no master match)
    merged = merged[merged["_merge"] != "right_only"].copy()

    # resolve parent_name / papername: prefer EFF (using) where present,
    # else the new master value.
    merged["parent_name"] = merged["parent_name_eff"].where(
        merged["parent_name_eff"].notna(), merged["parent_name_new"]
    )
    merged["papername"] = merged["papername_eff"].where(
        merged["papername_eff"].notna(), merged["papername_new"]
    )
    # newdata2023 = 1 where _merge==1 (left_only), else 0 (do-file 154-155)
    merged["newdata2023"] = np.where(merged["_merge"] == "left_only", 1.0, 0.0)

    # ``value`` (the variable kept downstream) is the master's value where it
    # exists, else the EFF value. We keep the ORIGINAL double (the .dta's
    # ``value`` column is read back by pyreadstat as the clean source double,
    # e.g. 47.6, not its float32 image). The float32 cast was only needed for
    # the merge KEY above.
    merged["value"] = merged["value_new"].where(
        merged["value_new"].notna(), merged["value_eff"]
    )
    # ``name`` in the .dta: Stata trims TRAILING blanks but preserves LEADING
    # ones (string storage convention). Missing names become empty strings.
    merged["name"] = merged["name"].where(merged["name"].notna(), "").astype(str).str.rstrip()

    out = merged[["metrics_name", "date", "name", "value", "parent_name",
                  "papername", "newdata2023"]].copy()
    # drop if date=="" (do-file 157)
    out = out[out["date"].astype(str).str.strip() != ""]
    return out.reset_index(drop=True)


def _build_axis_label(cfg) -> pd.DataFrame:
    """Build axis_label.dta: metrics metadata keyed on metrics_name (do-file 178-227).

    New metrics sheet (master) merged 1:1 with EFF metrics (using) on
    (metrics_name, parent_name). For overlapping keys the master (new) values
    win; EFF-only rows keep EFF values. Then keep
    (axis_label, metrics_name, scale, target, target_label).
    """
    mt = io.read_excel_sheet(cfg.raw_file("measures_metrics_newdata2023.xlsx"), sheet="metrics")
    new = mt[["axis_label", "metrics_name", "scale", "target", "target_label", "parent_name"]].copy()
    new = new[new["metrics_name"].notna() & (new["metrics_name"].astype(str).str.strip() != "")]

    eff = pd.read_csv(cfg.raw_file("metrics.csv")).rename(columns={"name": "metrics_name"})
    eff = eff[["metrics_name", "parent_name", "axis_label", "scale", "target", "target_label"]].copy()

    keys = ["metrics_name", "parent_name"]
    merged = new.merge(eff, on=keys, how="outer", suffixes=("", "_eff"), indicator=True)
    # For both/left rows, master (new) values win. For right_only (_merge==2),
    # use EFF values.
    right = merged["_merge"] == "right_only"
    for c in ["axis_label", "scale", "target", "target_label"]:
        merged.loc[right, c] = merged.loc[right, f"{c}_eff"]

    # axis_label.dta keeps these cols, dropna metrics_name (already filtered).
    al = merged[["axis_label", "metrics_name", "scale", "target", "target_label"]].copy()
    # metrics_name is unique across the merged metrics (verified), so m:1 merge
    # on metrics_name below is well-defined.
    al = al.drop_duplicates(subset=["metrics_name"]).reset_index(drop=True)
    return al


def _rescale(df: pd.DataFrame) -> pd.Series:
    """Per-metric rescaling by scale_type (do-file 297-329).

    Returns value_scaled. Each transform turns the raw benchmark value into a
    quantity that increases (roughly linearly) with AI capability.
    """
    scale = df["scale"]
    v = df["value"]
    vs = pd.Series(np.nan, index=df.index, dtype=float)

    # Percentage error / FID: -ln(v/100)  (decay toward 0 -> rising score)
    m = scale.isin(["Percentage error", "FID"])
    vs[m] = -np.log(v[m] / 100.0)
    # Percentage correct: -ln((100-v)/100)  (treat as the complementary error)
    m = scale == "Percentage correct"
    vs[m] = -np.log((100.0 - v[m]) / 100.0)
    # BLEU score: ln(v)
    m = scale == "BLEU score"
    vs[m] = np.log(v[m])
    # Score: ln(v) if v>0 ; -ln(-v) if v<0 ; 0 if v==0
    m = (scale == "Score") & (v > 0)
    vs[m] = np.log(v[m])
    m = (scale == "Score") & (v < 0)
    vs[m] = -np.log(-v[m])
    m = (scale == "Score") & (v == 0)
    vs[m] = 0.0
    # ELO rating: ln(v)
    m = scale == "ELO rating"
    vs[m] = np.log(v[m])
    # Perplexity: ln((1/v)*100)
    m = scale == "Perplexity"
    vs[m] = np.log((1.0 / v[m]) * 100.0)
    # Model Entropy: ln((1/2^v)*100)  (entropy -> perplexity = 2^entropy)
    m = scale == "Model Entropy"
    vs[m] = np.log((1.0 / (2.0 ** v[m])) * 100.0)
    return vs


# --------------------------------------------------------------------------- #
# Stage A: formated_data.dta                                                   #
# --------------------------------------------------------------------------- #

def build_formated_data(cfg) -> pd.DataFrame:
    """Reproduce formated_data.dta (do-file 230-353)."""
    measures = _build_measures(cfg)
    axis = _build_axis_label(cfg)

    # merge m:1 metrics_name (do-file 234); drop if missing(parent_name) (236).
    df = measures.merge(axis, on="metrics_name", how="left", indicator=True)
    df = df[df["parent_name"].notna()].copy()
    df["_merge"] = 3.0  # matches Stata: after drop, only _merge==3 remain (2108 rows)

    # --- threshold_label overrides (do-file 246-260) ---
    df["threshold_label"] = df["target_label"]
    df.loc[df["parent_name"] == "Simple video games", "threshold_label"] = "Human performance"
    df.loc[df["metrics_name"].isin(_HUMAN_PERF_METRICS), "threshold_label"] = "Human performance"

    # destring value/target (already numeric from sources)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["target"] = pd.to_numeric(df["target"], errors="coerce")

    # --- threshold dummy (do-file 276-282) ---
    # by metrics_name (date): dummy=1 if value>=target ; sumdummy=running sum;
    # threshold=1 on the FIRST surpassing observation; threshold_exists=1 if target!=.
    df = df.sort_values(["metrics_name", "date"], kind="mergesort").reset_index(drop=True)
    dummy = np.where(df["value"] >= df["target"], 1.0, np.nan)
    df["_dummy"] = dummy
    # running sum of dummy within metric (Stata sum() treats missing as 0)
    df["_sumdummy"] = (
        df.assign(_d=df["_dummy"].fillna(0.0))
        .groupby("metrics_name", sort=False)["_d"]
        .cumsum()
    )
    df["threshold"] = np.where((df["_dummy"] == 1.0) & (df["_sumdummy"] == 1.0), 1.0, np.nan)
    df["threshold_exists"] = np.where(df["target"].notna(), 1.0, np.nan)
    df = df.drop(columns=["_dummy", "_sumdummy"])

    # --- scale formatting overrides (do-file 292-295) ---
    # Top-5 error rate -> Percentage error, value*100
    m = df["axis_label"] == "Top-5 error rate"
    df.loc[m, "value"] = df.loc[m, "value"] * 100.0
    df.loc[m, "scale"] = "Percentage error"
    df.loc[df["axis_label"] == "Percentage correct", "scale"] = "Percentage correct"
    df.loc[df["metrics_name"] == "The Loebner Prize scored selection answers", "scale"] = "Percentage correct"

    # --- rescale (do-file 297-329) ---
    df["value_scaled"] = _rescale(df)

    # --- SOTA frontier (do-file 339-343) ---
    # gsort metrics_name date -value_scaled : within metric, sort by date asc,
    # then value_scaled desc (so ties on date take the higher scaled value first).
    df = df.sort_values(
        ["metrics_name", "date", "value_scaled"],
        ascending=[True, True, False],
        kind="mergesort",
    ).reset_index(drop=True)

    # current_max = running max of value_scaled within metric, in this order.
    # Stata: current_max = value_scaled (first row); else max(value_scaled[n],
    # current_max[n-1]). Stata's max() IGNORES missing, so a NaN-value_scaled row
    # CARRIES FORWARD the previous running max (it does not reset to NaN). pandas
    # cummax instead leaves the NaN row NaN, so we run the max over a -inf-filled
    # copy and restore NaN only where no non-missing value has yet appeared.
    vs = df["value_scaled"]
    run = vs.fillna(-np.inf).groupby(df["metrics_name"], sort=False).cummax()
    # rows before the first non-missing value_scaled stay missing
    seen = vs.notna().groupby(df["metrics_name"], sort=False).cummax().astype(bool)
    df["current_max"] = run.where(seen, np.nan)

    # frontier = 1 where current_max changes vs the previous row in the metric.
    # Stata's "!=" treats missing as the largest value, so missing==missing and
    # value!=missing. Thus the first row with a real current_max is a frontier
    # (value != prior-missing); a leading run of NaN current_max is not.
    prev = df.groupby("metrics_name", sort=False)["current_max"].shift(1)
    cm = df["current_max"].to_numpy()
    pv = prev.to_numpy()
    same = (cm == pv) | (np.isnan(cm) & np.isnan(pv))
    df["frontier"] = np.where(~same, 1.0, 0.0)

    # --- year / year_month (do-file 347-351) ---
    df["ym"] = df["date"].str.slice(0, 7)
    # Stata monthly index base 1960-01 = 0; we keep it numeric for the .dta.
    ym_dt = pd.to_datetime(df["ym"], format="%Y-%m")
    df["year_month"] = (ym_dt.dt.year - 1960) * 12 + (ym_dt.dt.month - 1)
    df["year_month"] = df["year_month"].astype(float)
    df["year"] = pd.to_numeric(df["date"].str.slice(0, 4), errors="coerce")

    return df.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Stage B: metrics_frontiers.dta                                              #
# --------------------------------------------------------------------------- #

def _yearly_index(cfg, measures: pd.DataFrame) -> pd.DataFrame:
    """Build yearly_index.dta: a (metrics_name, year) skeleton 1981..year_final
    with metricid (do-file 207-217).

    metricid = _n over the unique (metrics_name, parent_name) pairs *after
    duplicates drop*, in the order they appear in measures.dta.
    """
    base = measures[["metrics_name", "parent_name"]].drop_duplicates().reset_index(drop=True)
    base["metricid"] = np.arange(1, len(base) + 1)
    # expandcl ${year_final}-1980 -> (year_final-1980) copies per metric; then
    # year = 1980 + cumulative count within metric -> 1981 .. year_final.
    n_years = cfg.year_final - 1980
    years = np.arange(1981, cfg.year_final + 1)
    skel = base.loc[base.index.repeat(n_years)].reset_index(drop=True)
    skel["year"] = np.tile(years, len(base)).astype(float)
    return skel[["metrics_name", "year", "parent_name", "metricid"]]


def build_metrics_frontiers(cfg, formated: pd.DataFrame, measures: pd.DataFrame) -> pd.DataFrame:
    """Reproduce metrics_frontiers.dta (do-file 358-464)."""
    # --- collapse to (metrics_name, year): max of frontier metrics (do-file 361-362) ---
    g = (
        formated.groupby(["metrics_name", "year"], sort=True)
        .agg(
            current_max=("current_max", "max"),
            frontier=("frontier", "max"),
            threshold=("threshold", "max"),
            threshold_exists=("threshold_exists", "max"),
            threshold_label=("threshold_label", lambda s: s.dropna().iloc[0] if s.notna().any() else np.nan),
        )
        .reset_index()
    )

    # --- merge 1:1 with yearly_index skeleton (do-file 365) ---
    skel = _yearly_index(cfg, measures)
    df = skel.merge(g, on=["metrics_name", "year"], how="outer")
    df = df.rename(columns={"current_max": "cm"})

    # cmnew = cm if frontier==1 (do-file 372)
    df["cmnew"] = np.where(df["frontier"] == 1.0, df["cm"], np.nan)

    # --- restrict each metric to its observed year span (do-file 381-384) ---
    df["yearwithmetric"] = np.where(df["cm"].notna(), df["year"], np.nan)
    df["min_year_metric"] = df.groupby("metricid")["yearwithmetric"].transform("min")
    df["max_year_metric"] = df.groupby("metricid")["yearwithmetric"].transform("max")
    df = df[(df["year"] >= df["min_year_metric"]) & (df["year"] <= df["max_year_metric"])].copy()

    # sort as a tsset panel by metricid, year
    df = df.sort_values(["metricid", "year"], kind="mergesort").reset_index(drop=True)

    # lag helpers within metricid (panel respects only contiguous years because
    # the skeleton fills every year, so simple shift == Stata L. operator).
    def lag(col, k):
        s = df.groupby("metricid", sort=False)[col].shift(k)
        same = df.groupby("metricid", sort=False)["metricid"].shift(k) == df["metricid"]
        return s.where(same)

    cmnew = df["cmnew"]
    Lid = {k: df.groupby("metricid", sort=False)["metricid"].shift(k) for k in range(1, 8)}
    Lc = {k: lag("cmnew", k) for k in range(1, 8)}

    # --- glapp: years since last SOTA jump (do-file 386-392) ---
    glapp = pd.Series(np.nan, index=df.index)
    cur_notna = cmnew.notna()
    # glapp=2..8 progressively; later assignments overwrite (Stata replace order)
    cond2 = cur_notna & Lc[1].isna() & (df["metricid"] == Lid[1])
    glapp[cond2] = 2
    cond3 = cur_notna & Lc[1].isna() & Lc[2].isna() & (df["metricid"] == Lid[2])
    glapp[cond3] = 3
    cond4 = cond3 & Lc[3].isna() & (df["metricid"] == Lid[3])
    glapp[cond4] = 4
    cond5 = cond4 & Lc[4].isna() & (df["metricid"] == Lid[4])
    glapp[cond5] = 5
    cond6 = cond5 & Lc[5].isna() & (df["metricid"] == Lid[5])
    glapp[cond6] = 6
    cond7 = cond6 & Lc[6].isna() & (df["metricid"] == Lid[6])
    glapp[cond7] = 7
    cond8 = cond7 & Lc[7].isna() & (df["metricid"] == Lid[7])
    glapp[cond8] = 8
    df["glapp"] = glapp

    # --- delta: year-on-year change when there is no gap (glapp missing) (do-file 402-403) ---
    df["delta"] = np.nan
    nogap = df["glapp"].isna()
    df.loc[nogap, "delta"] = (cmnew - Lc[1])[nogap]

    # --- deltanew: spread a jump evenly across the gap years (do-file 404-419) ---
    df["deltanew"] = np.nan
    # We must apply these in the same sequential order as Stata, using ALREADY
    # updated deltanew for the F-operator forward fills.
    g_ = df["glapp"]

    def setF(target_mask, source_shift):
        """deltanew = F{k}.deltanew where the future row k ahead has glapp==g."""
        src = df.groupby("metricid", sort=False)["deltanew"].shift(-source_shift)
        same = df.groupby("metricid", sort=False)["metricid"].shift(-source_shift) == df["metricid"]
        df.loc[target_mask, "deltanew"] = src.where(same)[target_mask]

    # glapp==2
    df.loc[g_ == 2, "deltanew"] = ((cmnew - Lc[2]) / 2)[g_ == 2]
    setF(df.groupby("metricid", sort=False)["glapp"].shift(-1) == 2, 1)
    # glapp==3
    df.loc[g_ == 3, "deltanew"] = ((cmnew - Lc[3]) / 3)[g_ == 3]
    setF(df.groupby("metricid", sort=False)["glapp"].shift(-1) == 3, 1)
    setF(df.groupby("metricid", sort=False)["glapp"].shift(-2) == 3, 2)
    # glapp==4
    df.loc[g_ == 4, "deltanew"] = ((cmnew - Lc[4]) / 4)[g_ == 4]
    setF(df.groupby("metricid", sort=False)["glapp"].shift(-1) == 4, 1)
    setF(df.groupby("metricid", sort=False)["glapp"].shift(-2) == 4, 2)
    setF(df.groupby("metricid", sort=False)["glapp"].shift(-3) == 4, 3)
    # glapp==5
    df.loc[g_ == 5, "deltanew"] = ((cmnew - Lc[5]) / 5)[g_ == 5]
    setF(df.groupby("metricid", sort=False)["glapp"].shift(-1) == 5, 1)
    setF(df.groupby("metricid", sort=False)["glapp"].shift(-2) == 5, 2)
    setF(df.groupby("metricid", sort=False)["glapp"].shift(-3) == 5, 3)
    setF(df.groupby("metricid", sort=False)["glapp"].shift(-4) == 5, 4)

    # --- deltafinal (do-file 422-428) ---
    df["delta"] = df["delta"].fillna(0.0)
    df["deltanew"] = df["deltanew"].fillna(0.0)
    df["deltafinal"] = np.nan
    df.loc[df["delta"] > 0, "deltafinal"] = df.loc[df["delta"] > 0, "delta"]
    df.loc[df["deltanew"] > 0, "deltafinal"] = df.loc[df["deltanew"] > 0, "deltanew"]
    # replace deltafinal=0 if missing & metricid==L1.metricid (do-file 428):
    # i.e. not the first row of the metric panel.
    not_first = (df["metricid"] == Lid[1])
    df.loc[df["deltafinal"].isna() & not_first, "deltafinal"] = 0.0

    # --- mean & count of deltafinal per (parent_name, year) (do-file 460-461) ---
    df["mean"] = df.groupby(["parent_name", "year"])["deltafinal"].transform("mean")
    df["count"] = df.groupby(["parent_name", "year"])["deltafinal"].transform("count").astype(float)

    # restore column order to match the target .dta
    cols = ["metrics_name", "year", "cm", "frontier", "threshold", "threshold_exists",
            "threshold_label", "parent_name", "metricid", "cmnew", "yearwithmetric",
            "glapp", "delta", "deltanew", "deltafinal", "mean", "count"]
    df["metricid"] = df["metricid"].astype(float)
    return df[cols].reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Stage C: slopes + slopes_slimmed_<app>                                       #
# --------------------------------------------------------------------------- #

def build_slopes(cfg, frontiers: pd.DataFrame) -> pd.DataFrame:
    """Collapse metrics_frontiers to (parent_name, year) and add robotics row
    (do-file 466-484)."""
    slopes = (
        frontiers.groupby(["parent_name", "year"], sort=True)
        .agg(
            mean=("mean", "max"),
            count=("count", "max"),
            threshold=("threshold", "max"),
            threshold_exists=("threshold_exists", "max"),
            threshold_label=("threshold_label", lambda s: s.dropna().iloc[0] if s.notna().any() else np.nan),
        )
        .reset_index()
    )
    slopes = slopes[slopes["mean"].notna()].copy()  # drop if mean==. (do-file 468)

    # append the dummy robotics row (do-file 477-484)
    rob = pd.DataFrame(
        {
            "year": [float(cfg.year_final)],
            "parent_name": ["robotics"],
            "count": [1.0],
            "mean": [1.0],
        }
    )
    slopes = pd.concat([slopes, rob], ignore_index=True)
    return slopes


def build_slimmed(cfg, slopes: pd.DataFrame, category: str) -> pd.DataFrame:
    """Reproduce slopes_slimmed_<category>.dta (do-file 497-587)."""
    df = slopes.copy()
    df = df.sort_values(["parent_name", "year"], kind="mergesort").reset_index(drop=True)
    df = df[df["year"] >= 2010].copy()  # do-file 501

    df["application"] = df["parent_name"].map(_APP_NAME)
    df["application_id"] = df["application"].map(_APP_ID)

    keep_ids = _CATEGORY_IDS[category]
    df = df[df["application_id"].isin(keep_ids)].copy()
    df = df.drop(columns=["application_id"])

    # target column order matches the .dta
    cols = ["year", "parent_name", "count", "mean", "threshold",
            "threshold_exists", "threshold_label", "application"]
    return df[cols].reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Orchestration                                                                #
# --------------------------------------------------------------------------- #

def run(cfg, validate: bool = True):  # noqa: A002 (mirror the prompt's signature)
    from . import validate as _v

    measures = _build_measures(cfg)
    formated = build_formated_data(cfg)
    frontiers = build_metrics_frontiers(cfg, formated, measures)
    slopes = build_slopes(cfg, frontiers)

    # --- write checkpoints for all 13 categories (stage 4 consumes these) ---
    slimmed = {}
    for cat in _CATEGORY_IDS:
        s = build_slimmed(cfg, slopes, cat)
        slimmed[cat] = s
        s.to_parquet(cfg.out_file(f"slopes_slimmed_{cat}.parquet"), index=False)
    # also persist the two intermediates downstream might want
    formated.to_parquet(cfg.out_file("formated_data.parquet"), index=False)
    frontiers.to_parquet(cfg.out_file("metrics_frontiers.parquet"), index=False)

    if not validate:
        return []

    results = []
    # 1) formated_data: validates the ~10 transforms (value_scaled) + frontier
    results.append(
        _v.compare_to_dta(
            formated,
            cfg.enriched_ref_file("formated_data.dta"),
            keys=["metrics_name", "date", "name", "value"],
            value_cols=["value_scaled", "current_max", "frontier", "value", "year"],
            tol=cfg.tol_internal,
            name="formated_data.dta",
        )
    )
    # 2) metrics_frontiers: validates frontier + gap logic (deltafinal, glapp)
    results.append(
        _v.compare_to_dta(
            frontiers,
            cfg.enriched_ref_file("metrics_frontiers.dta"),
            keys=["metrics_name", "year"],
            value_cols=["cm", "cmnew", "glapp", "delta", "deltanew", "deltafinal", "mean", "count"],
            tol=cfg.tol_internal,
            name="metrics_frontiers.dta",
        )
    )
    # 3) PRIMARY Delta p_it: slopes_slimmed_allapps + genai + one single-app
    results.append(
        _v.compare_to_dta(
            slimmed["allapps"],
            cfg.enriched_ref_file("slopes_slimmed_allapps.dta"),
            keys=["application", "year"],
            value_cols=["mean", "count"],
            tol=cfg.tol_internal,
            name="slopes_slimmed_allapps.dta",
        )
    )
    results.append(
        _v.compare_to_dta(
            slimmed["genai"],
            cfg.enriched_ref_file("slopes_slimmed_genai.dta"),
            keys=["application", "year"],
            value_cols=["mean", "count"],
            tol=cfg.tol_internal,
            name="slopes_slimmed_genai.dta",
        )
    )
    results.append(
        _v.compare_to_dta(
            slimmed["lngmod"],
            cfg.enriched_ref_file("slopes_slimmed_lngmod.dta"),
            keys=["application", "year"],
            value_cols=["mean", "count"],
            tol=cfg.tol_internal,
            name="slopes_slimmed_lngmod.dta",
        )
    )
    return results
