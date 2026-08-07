"""
MASTER PIPELINE — Annual Δp (Eq. 2) and Cumulative = Sum of ΔDAIOE (Eq. 6)

End-to-end, pure Python. Heavy inline comments for non-programmers.

Order of work:
  0) Standardize application names to FRS terminology.
  1) Build "anchors" (high/low) per ability using FRS “Combined” (max/min per ability).
  2) Estimate a 9×58 application–ability mapping (LLM-based) and save it.
  3) Validate our mapping vs FRS “Combined” and report similarity.
  4) Build occupation-by-ability weights from O*NET (Importance × Level).
  5) Compute exposure variants (A: no social down-weight; B: DAIOE-style) and compare with original DAIOE.
  6) Compute ΔDAIOE (Eq. 3, robustness variant) for a chosen year using **annual** Δp from raw_data/delta_progress.csv:
       Δe_{o,t} = sum_i Δp_{i,t} · (sum_j r_{o,j} x_{i,j})
       ΔDAIOE_{o,t} = (Δe_{o,t})^2           (no social discounting in robustness variant)
     Here r_{o,j} = (i_{o,j} · l_{o,j}) / sum_{j=1}^{52} (i_{o,j} · l_{o,j}) per Eq. (1) using the 52 abilities only.
  7) Compute the **level** DAIOE per Eq. (6) as the running sum of yearly ΔDAIOE:
       DAIOE_{o,t} = sum_{τ≤t} ΔDAIOE_{o,τ}
     (No cumulative-progress input is needed; we build from the annual Δp file.)

Inputs:
  - raw_data/applications.csv
  - raw_data/abilities.csv
  - Abilities.xlsx, Skills.xlsx
  - mapping_matrix.xlsx (sheet “Combined”)
  - daioe_onetsoc2010.csv (TSV)
  - raw_data/delta_progress.csv  (long annual file: ai_app_id/name, year, delta_p)

Outputs:
  - mapping_matrix_9x58_v2018.csv
  - comparison_our_vs_frs_v2018.csv
  - final_exposure_comparison.csv
  - new_daioe_<YEAR>.csv                      <-- Eq. (3), ΔDAIOE for <YEAR> (robustness variant, no discount)
  - new_daioe_cumulative_<YEAR>.csv           <-- Eq. (6), DAIOE level up to <YEAR> (sum of ΔDAIOE)
  - new_daioe_timeseries.csv                  <-- panel with Δe, ΔDAIOE, and cumulative DAIOE by year
  - final_exposure_comparison_with_new_and_cumulative_daioe.csv
  - summary.json, summary_tables.csv
"""
from __future__ import annotations
from pathlib import Path
import sys, os, importlib.util, json
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW  = ROOT/"raw_data"
MOD  = ROOT/"mod_data"
OUT  = ROOT/"output"
for p in (RAW, MOD, OUT):
    p.mkdir(exist_ok=True)

# --- All inputs now under raw_data/ ---
FRS_COMBINED_XLSX = RAW/"mapping_matrix.xlsx"
APPS_CSV          = RAW/"applications.csv"
ABILITIES_CSV     = RAW/"abilities.csv"
ANCHORS_CSV       = RAW/"anchors.csv"
ABILITIES_XLSX    = RAW/"Abilities.xlsx"
SKILLS_XLSX       = RAW/"Skills.xlsx"
DAIOE_TSV         = RAW/"daioe_onetsoc2010.csv"  # TSV
DELTA_LONG_CSV    = RAW/"delta_progress.csv"

DEFAULT_VANTAGE   = "2018"
MAPPING_OUT       = OUT/f"mapping_matrix_9x58_v{DEFAULT_VANTAGE}.csv"

FRS9 = [
    "abstract strategy games",
    "real-time video games",
    "image recognition",
    "visual question answering",
    "generating images",
    "reading comprehension",
    "language modeling",
    "translation",
    "speech recognition",
]

def _cols_to_int_if_numeric(cols):
    out = []
    for c in cols:
        try:
            out.append(int(c))
        except Exception:
            out.append(c)
    return out

def _import_from_path(py_path: Path):
    spec = importlib.util.spec_from_file_location(py_path.stem, py_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod

def _print_header(msg: str):
    print("\n" + "="*80)
    print(msg)
    print("="*80)

# === STEP 0: Standardize applications ===
def standardize_applications(apps_csv: Path) -> pd.DataFrame:
    apps = pd.read_csv(apps_csv)
    alias = {
        "Image comprehension": "Visual question answering",
        "Image generation": "Generating images",
        "Language modelling": "Language modeling",
        "Real‑time video games": "Real-time video games",
    }
    if "name" in apps.columns:
        apps["name"] = apps["name"].replace(alias)
    if "ai_app_id" not in apps.columns and "id" in apps.columns:
        apps = apps.rename(columns={"id":"ai_app_id"})
    if "ai_app_id" not in apps.columns:
        apps = apps.assign(ai_app_id=range(1, len(apps)+1))
    apps = apps[["ai_app_id","name"]]
    apps.to_csv(apps_csv, index=False)
    return apps

# === STEP 1: Anchors from FRS (max/min per ability) ===
def generate_anchors_from_frs(apps: pd.DataFrame, abilities_csv: Path, frs_combined_xlsx: Path, anchors_csv: Path) -> pd.DataFrame:
    abilities = pd.read_csv(abilities_csv)
    combined = pd.read_excel(frs_combined_xlsx, sheet_name="Combined")
    combined9 = combined[combined["abilities"].isin(FRS9)].copy()

    name_to_ability_id = {r["ability_name"].strip().lower(): int(r["ability_id"]) for _, r in abilities.iterrows() if int(r["ability_id"])<=58}
    ability_cols = [c for c in combined9.columns if c not in ["ability_id","abilities"]]
    col_to_ability_id = {}
    for col in ability_cols:
        key = str(col).strip().lower()
        if key in name_to_ability_id:
            col_to_ability_id[col] = name_to_ability_id[key]

    app_name_to_id = dict(zip(apps["name"].str.lower(), apps["ai_app_id"]))

    templ = {
        "abstract strategy games": "Search/planning over discrete states; strong mapping to rule-based reasoning/patterns.",
        "real-time video games": "Rapid perception–action cycles, multitasking in dynamic environments.",
        "image recognition": "Detects/categorizes visual objects; limited for non-visual abilities.",
        "visual question answering": "Integrates vision & language to answer questions about images (multimodal reasoning).",
        "generating images": "Synthesizes images from prompts; supports creativity/visualization.",
        "reading comprehension": "Extracts meaning and evidence from text; aligns with text-based reasoning.",
        "language modeling": "Predicts/follows instructions in text; supports language-centric abilities.",
        "translation": "Maps meaning across languages; strong for textual expression/comprehension.",
        "speech recognition": "Transcribes speech; aligns with auditory/speech perception.",
    }

    # Long app–ability table
    rows_long = []
    for _, row in combined9.iterrows():
        app_name = str(row["abilities"]).strip().lower()
        for col, val in row.items():
            if col in col_to_ability_id and pd.notnull(val):
                rows_long.append({
                    "app_name": app_name,
                    "ai_app_id": app_name_to_id.get(app_name, np.nan),
                    "ability_id": col_to_ability_id[col],
                    "score": float(val),
                })
    long = pd.DataFrame(rows_long)

    rows = []
    # abilities 1..52 from FRS max/min
    for a_id in sorted([int(a) for a in abilities["ability_id"].unique() if 1 <= int(a) <= 52]):
        g = long[long["ability_id"]==a_id]
        if g.empty:
            continue
        high = g.loc[g["score"].idxmax()]
        low  = g.loc[g["score"].idxmin()]
        ab_row = abilities.loc[abilities["ability_id"]==a_id].iloc[0]
        ab_name = ab_row["ability_name"]
        ab_def  = str(ab_row["ability_definition"]).lower()
        high_note = f"[{high['app_name']}] {templ.get(high['app_name'], high['app_name'].capitalize())} — engages '{ab_name}': {ab_def} (FRS≈{high['score']:.2f})."
        low_note  = f"[{low['app_name']}] {templ.get(low['app_name'], low['app_name'].capitalize())} — little for '{ab_name}', unrelated to {ab_def} (FRS≈{low['score']:.2f})."
        rows += [
            {"ai_app_id": int(high["ai_app_id"]) if not np.isnan(high["ai_app_id"]) else None, "ability_id": a_id, "label": "high", "note": high_note},
            {"ai_app_id": int(low["ai_app_id"])  if not np.isnan(low["ai_app_id"])  else None, "ability_id": a_id, "label": "low",  "note": low_note},
        ]

    # social skills 53..58 (simple heuristic)
    hi_apps = ["language modeling","reading comprehension","speech recognition","translation"]
    lo_apps = ["image recognition","abstract strategy games","generating images","real-time video games"]
    for a_id in range(53, 59):
        ab_row = abilities.loc[abilities["ability_id"]==a_id].iloc[0]
        ab_name = ab_row["ability_name"]
        ab_def  = str(ab_row["ability_definition"]).lower()
        ha = next((n for n in hi_apps if n in app_name_to_id), hi_apps[0])
        la = next((n for n in lo_apps if n in app_name_to_id), lo_apps[0])
        rows += [
            {"ai_app_id": int(app_name_to_id[ha]), "ability_id": a_id, "label": "high",
             "note": f"[{ha}] Text/speech cues support '{ab_name}': {ab_def}."},
            {"ai_app_id": int(app_name_to_id[la]), "ability_id": a_id, "label": "low",
             "note": f"[{la}] Visual/control tasks provide little for '{ab_name}', unrelated to {ab_def}."},
        ]

    anchors = pd.DataFrame(rows).sort_values(["ability_id","label"])
    anchors.to_csv(anchors_csv, index=False)
    return anchors

# === STEP 2: Estimate mapping (calls external script) ===
def run_estimate_mapping(vantage: str = DEFAULT_VANTAGE, model_primary=None, model_secondary=None) -> Path:
    script = ROOT/"code"/"estimate_mapping.py"
    if not script.exists():
        raise FileNotFoundError(f"Missing {script}")
    mod = _import_from_path(script)
    argv_bak = sys.argv[:]
    sys.argv = ["estimate_mapping.py", "--vantage", vantage]
    if model_primary:
        os.environ["MODEL_PRIMARY"] = model_primary
    if model_secondary:
        os.environ["MODEL_SECONDARY"] = model_secondary
    try:
        mod.main()  # type: ignore
    finally:
        sys.argv = argv_bak
    out_path = OUT/f"mapping_matrix_9x58_v{vantage}.csv"
    if not out_path.exists():
        raise RuntimeError(f"Expected mapping output not found: {out_path}")
    return out_path

# === STEP 3: Validate vs FRS (calls external script) ===
def run_validate_against_frs(vantage: str = DEFAULT_VANTAGE) -> Path:
    script = ROOT/"code"/"validate_against_frs.py"
    if not script.exists():
        raise FileNotFoundError(f"Missing {script}")
    mod = _import_from_path(script)
    argv_bak = sys.argv[:]
    sys.argv = ["validate_against_frs.py", "--vantage", vantage]
    try:
        mod.main()  # type: ignore
    finally:
        sys.argv = argv_bak
    comp_path = OUT/f"comparison_our_vs_frs_v{vantage}.csv"
    return comp_path

# === STEP 4: O*NET weights ===
def build_occ_ability_weights(abilities_xlsx: Path, skills_xlsx: Path, abilities_csv: Path, out_csv: Path) -> pd.DataFrame:
    abil = pd.read_excel(abilities_xlsx)
    skil = pd.read_excel(skills_xlsx)
    abil_imp = abil[abil["Scale Name"].str.contains("Importance", case=False)]
    abil_lvl = abil[abil["Scale Name"].str.contains("Level", case=False)]
    skil_imp = skil[skil["Scale Name"].str.contains("Importance", case=False)]
    skil_lvl = skil[skil["Scale Name"].str.contains("Level", case=False)]

    def _pivot(df):
        return df.pivot_table(index="O*NET-SOC Code", columns="Element Name", values="Data Value", aggfunc="mean")

    A_imp_w = _pivot(abil_imp); A_lvl_w = _pivot(abil_lvl)
    S_imp_w = _pivot(skil_imp); S_lvl_w = _pivot(skil_lvl)

    imp_w = pd.concat([A_imp_w, S_imp_w], axis=1)
    lvl_w = pd.concat([A_lvl_w, S_lvl_w], axis=1)

    def _norm01(x: pd.Series):
        xmin, xmax = np.nanmin(x.values), np.nanmax(x.values)
        if not np.isfinite(xmin) or not np.isfinite(xmax) or xmax<=xmin:
            return pd.Series(np.zeros_like(x), index=x.index)
        return (x - xmin) / (xmax - xmin)

    imp_n = imp_w.apply(_norm01, axis=0)
    lvl_n = lvl_w.apply(_norm01, axis=0)

    W = (imp_n.fillna(0.0) * lvl_n.fillna(0.0))

    abilities = pd.read_csv(abilities_csv)
    name_to_id = {r["ability_name"].strip().lower(): int(r["ability_id"]) for _, r in abilities.iterrows()}
    cols_keep = [c for c in W.columns if str(c).strip().lower() in name_to_id]
    W = W[cols_keep].copy()
    W.columns = [name_to_id[str(c).strip().lower()] for c in cols_keep]
    for k in range(1, 59):
        if k not in W.columns:
            W[k] = 0.0
    W = W[[k for k in range(1,59)]]
    W = W.reset_index().rename(columns={"O*NET-SOC Code":"occ"})
    W.to_csv(out_csv, index=False)
    return W

# === Helper: exposure computation (imported or inline fallback) ===
def _compute_exposure_helper():
    coe_path = ROOT/"code"/"compute_occupation_exposure.py"
    if not coe_path.exists():
        from textwrap import dedent
        coe_code = dedent("""
        import numpy as np, pandas as pd
        SOCIAL_IDS = list(range(53,59))
        def compute_exposure(M: pd.DataFrame, W: pd.DataFrame, gamma: float = 1.0, delta: float = 2.0):
            abil = [c for c in W.columns if c in M.columns]
            M2 = M[abil].copy(); W2 = W[abil].copy()
            E_matrix = W2.values.dot(M2.T.values)
            occ_index = W2.index
            E_A = pd.Series(E_matrix.sum(axis=1), index=occ_index, name="exposure_A")
            soc_cols = [c for c in abil if c in SOCIAL_IDS]
            if soc_cols:
                E_soc = W2[soc_cols].values.dot(M2[soc_cols].T.values).sum(axis=1)
            else:
                E_soc = np.zeros(len(occ_index))
            denom = np.where(E_A.values>0, E_A.values, np.nan)
            s_share = pd.Series(E_soc / denom, index=occ_index).fillna(0.0).clip(0.0, 1.0)
            s_share.name = "social_share"
            E_B = E_A / (1.0 + delta * s_share.values)**gamma
            E_B = pd.Series(E_B, index=occ_index, name="exposure_B")
            return E_A, E_B, s_share
        """)
        coe_path.write_text(coe_code, encoding="utf-8")
    mod = _import_from_path(coe_path)
    return mod

# === STEP 5: Exposures and comparison ===
def compute_exposures_and_compare(mapping_csv: Path, occ_ability_csv: Path, daioe_tsv: Path, out_csv: Path, gamma=1.0, delta=2.0) -> pd.DataFrame:
    coe = _compute_exposure_helper()
    M = pd.read_csv(mapping_csv)
    def _col_to_int(c):
        try:
            return int(c)
        except:
            return c
    M.columns = [_col_to_int(c) for c in M.columns]
    if "ai_app_id" in M.columns:
        M = M.set_index("ai_app_id")
    elif "abilities" in M.columns:
        M = M.set_index("abilities")
    else:
        M.index = range(1, len(M)+1)

    W = pd.read_csv(occ_ability_csv)
    W.columns = _cols_to_int_if_numeric(W.columns)
    W = W.set_index("occ")

    E_A, E_B, s_share = coe.compute_exposure(M, W, gamma=gamma, delta=delta)
    out = pd.DataFrame({
        "occ": E_A.index,
        "exposure_A": E_A.values,
        "exposure_B": E_B.values,
        "social_share": s_share.values,
    })

    def pct_rank(x):
        return 100.0 * (x.rank(method="average") - 1) / (len(x) - 1) if len(x)>1 else 100.0
    out["pctl_A"] = pct_rank(out["exposure_A"])
    out["pctl_B"] = pct_rank(out["exposure_B"])

    da = pd.read_csv(daioe_tsv, sep="\t")
    da = da.sort_values("year").drop_duplicates(subset=["occ_code_onetsoc2010"], keep="last")
    da = da.rename(columns={"occ_code_onetsoc2010":"occ"})
    cols_keep = ["occ","occ_title_onetsoc2010","daioe_allapps","pctl_rank_allapps"]
    cols_keep = [c for c in cols_keep if c in da.columns]
    da = da[cols_keep]

    m = pd.merge(out, da, on="occ", how="inner")
    if m.shape[0]>2 and "pctl_rank_allapps" in m.columns:
        m["corr_A_vs_DAIOE"] = np.corrcoef(m["pctl_A"], m["pctl_rank_allapps"])[0,1]
        m["corr_B_vs_DAIOE"] = np.corrcoef(m["pctl_B"], m["pctl_rank_allapps"])[0,1]
    m = m.sort_values("pctl_A", ascending=False)
    m.to_csv(out_csv, index=False)
    return m

# === Helper for Eq.(1): r_{o,j} from W (52 abilities only) ===
def _normalize_to_r(W: pd.DataFrame) -> pd.DataFrame:
    """
    Convert occ×ability weights W into r_{o,j} shares over the 52 abilities.
    We ignore the 6 social skills here (Eq. 1 uses j=1..52).
    """
    abil_52 = [c for c in W.columns if isinstance(c, (int, np.integer)) and 1 <= c <= 52]
    R = W[abil_52].copy()
    denom = R.sum(axis=1).replace(0.0, np.nan)
    R = R.div(denom, axis=0).fillna(0.0)
    return R

# === STEP 6: Eq.(3) from ANNUAL Δp (robustness variant, no social discount) ===
def compute_new_daioe_from_progress(mapping_csv: Path, occ_ability_csv: Path, delta_progress_csv: Path, out_csv: Path, target_year: int = None):
    """
    Compute ΔDAIOE for a given year based on annual Δp (Eq. 2→3), without social discount:
      Δe_{o,t} = sum_i Δp_{i,t} · (sum_j r_{o,j} x_{i,j})
      ΔDAIOE_{o,t} = (Δe_{o,t})^2
    If target_year is None and the file has multiple years, we pick the latest.
    Missing app-year entries -> 0 for that year.
    """
    M = pd.read_csv(mapping_csv)
    def _col_to_int(c):
        try:
            return int(c)
        except:
            return c
    M.columns = [_col_to_int(c) for c in M.columns]
    if "ai_app_id" in M.columns:
        M = M.set_index("ai_app_id")
    elif "abilities" in M.columns:
        M = M.set_index("abilities")
    else:
        M.index = range(1, len(M)+1)

    # Use only the 52 abilities for Eq.(1–3)
    abil_52 = [c for c in M.columns if isinstance(c, (int, np.integer)) and 1 <= c <= 52]
    M52 = M[abil_52].copy()

    W = pd.read_csv(occ_ability_csv)
    W.columns = _cols_to_int_if_numeric(W.columns)
    W = W.set_index("occ")

    R = _normalize_to_r(W)  # r_{o,j} shares (sum over 52 = 1 for each occ)

    # Exposure kernel sum_j r_{o,j} x_{i,j}  => occ×apps
    E_kernel = R.values.dot(M52.T.values)
    occ_index = R.index
    app_index = M52.index
    E = pd.DataFrame(E_kernel, index=occ_index, columns=app_index)

    dp = pd.read_csv(delta_progress_csv)

    # map app names -> ids
    apps = pd.read_csv(APPS_CSV)
    alias = {
        "Image comprehension": "Visual question answering",
        "Image generation": "Generating images",
        "Language modelling": "Language modeling",
        "Real‑time video games": "Real-time video games",
    }
    if "name" in apps.columns:
        apps["name"] = apps["name"].replace(alias)
    if "ai_app_id" not in apps.columns and "id" in apps.columns:
        apps = apps.rename(columns={"id":"ai_app_id"})
    name_to_id = dict(zip(apps["name"].str.lower(), apps["ai_app_id"]))

    if "ai_app_id" not in dp.columns:
        if "name" in dp.columns:
            dp["ai_app_id"] = dp["name"].astype(str).str.lower().map(name_to_id)
        elif any(c.lower()=="application" for c in dp.columns):
            app_col = [c for c in dp.columns if c.lower()=="application"][0]
            dp["ai_app_id"] = dp[app_col].astype(str).str.lower().map(name_to_id)
        else:
            raise ValueError("delta_progress file must have 'ai_app_id' or 'name'/'application' column.")

    # Choose year
    if "year" in dp.columns:
        years = pd.to_numeric(dp["year"], errors="coerce").dropna().astype(int)
        if target_year is None:
            target_year = int(years.max())
        dp = dp[pd.to_numeric(dp["year"], errors="coerce")==target_year].copy()
    else:
        if target_year is None:
            target_year = 2023  # assume single-year file

    # Find delta_p column
    delta_col = None
    for cand in ["delta_p","delta","delta_progress","delta_progress_"+str(target_year),"deltap","dp"]:
        if cand in dp.columns:
            delta_col = cand
            break
    if delta_col is None:
        non_id_cols = [c for c in dp.columns if c not in ["ai_app_id","name","application","year"]]
        if not non_id_cols:
            raise ValueError("delta_progress file missing delta column (e.g., 'delta_p').")
        delta_col = non_id_cols[0]

    # Align Δp to app index; missing app-year = 0
    dp_aligned = pd.Series(0.0, index=app_index, dtype=float)
    m = dp.dropna(subset=["ai_app_id"]).set_index("ai_app_id")[delta_col]
    inter = dp_aligned.index.intersection(m.index)
    dp_aligned.loc[inter] = pd.to_numeric(m.loc[inter], errors="coerce").fillna(0.0).values

    delta_e = E.values.dot(dp_aligned.values)
    delta_daioe = np.square(delta_e)

    out = pd.DataFrame({
        "occ": occ_index,
        f"delta_e_{target_year}": delta_e,
        f"delta_DAIOE_{target_year}": delta_daioe,
    }).set_index("occ")

    def pct_rank(x):
        return 100.0 * (x.rank(method="average") - 1) / (len(x) - 1) if len(x)>1 else 100.0
    out[f"pctl_new_{target_year}"] = pct_rank(out[f"delta_DAIOE_{target_year}"])

    out = out.reset_index()
    out.to_csv(out_csv, index=False)
    return out, target_year

# === STEP 7: Eq.(6) level = sum of yearly ΔDAIOE (no separate cumulative input) ===
def compute_daioe_level_timeseries(mapping_csv: Path, occ_ability_csv: Path, delta_progress_csv: Path, out_snapshot_csv: Path, out_timeseries_csv: Path, target_year: int = None):
    """
    Build yearly ΔDAIOE from annual Δp for all years, then cumulate over time:
      Δe_{o,t} = sum_i Δp_{i,t} · (sum_j r_{o,j} x_{i,j})
      ΔDAIOE_{o,t} = (Δe_{o,t})^2
      DAIOE_{o,t}  = sum_{τ≤t} ΔDAIOE_{o,τ}
    Writes:
      - out_timeseries_csv: long panel (occ, year, delta_e, delta_DAIOE, DAIOE_cum, pctl_cum)
      - out_snapshot_csv: snapshot at target_year (or latest if None), with columns suffixed by year.
    """
    M = pd.read_csv(mapping_csv)
    def _col_to_int(c):
        try:
            return int(c)
        except:
            return c
    M.columns = [_col_to_int(c) for c in M.columns]
    if "ai_app_id" in M.columns:
        M = M.set_index("ai_app_id")
    elif "abilities" in M.columns:
        M = M.set_index("abilities")
    else:
        M.index = range(1, len(M)+1)
    abil_52 = [c for c in M.columns if isinstance(c, (int, np.integer)) and 1 <= c <= 52]
    M52 = M[abil_52].copy()

    W = pd.read_csv(occ_ability_csv)
    W.columns = _cols_to_int_if_numeric(W.columns)
    W = W.set_index("occ")

    R = _normalize_to_r(W)

    # Exposure kernel (occ×apps)
    E_kernel = R.values.dot(M52.T.values)
    occ_index = R.index
    app_index = M52.index
    E = pd.DataFrame(E_kernel, index=occ_index, columns=app_index)

    dp = pd.read_csv(delta_progress_csv)

    # Map app names -> ids
    apps = pd.read_csv(APPS_CSV)
    alias = {
        "Image comprehension": "Visual question answering",
        "Image generation": "Generating images",
        "Language modelling": "Language modeling",
        "Real‑time video games": "Real-time video games",
    }
    if "name" in apps.columns:
        apps["name"] = apps["name"].replace(alias)
    if "ai_app_id" not in apps.columns and "id" in apps.columns:
        apps = apps.rename(columns={"id":"ai_app_id"})
    name_to_id = dict(zip(apps["name"].str.lower(), apps["ai_app_id"]))

    if "ai_app_id" not in dp.columns:
        if "name" in dp.columns:
            dp["ai_app_id"] = dp["name"].astype(str).str.lower().map(name_to_id)
        elif any(c.lower()=="application" for c in dp.columns):
            app_col = [c for c in dp.columns if c.lower()=="application"][0]
            dp["ai_app_id"] = dp[app_col].astype(str).str.lower().map(name_to_id)
        else:
            raise ValueError("delta_progress file must have 'ai_app_id' or 'name'/'application' column.")

    if "year" not in dp.columns:
        raise ValueError("delta_progress.csv must contain a 'year' column for Eq. (6).")

    dp = dp.dropna(subset=["ai_app_id","year"])
    dp["year"] = pd.to_numeric(dp["year"], errors="coerce").astype("Int64")
    dp = dp.dropna(subset=["year"])
    dp["year"] = dp["year"].astype(int)

    # Identify delta_p column
    delta_col = None
    for cand in ["delta_p","delta","delta_progress","deltap","dp"]:
        if cand in dp.columns:
            delta_col = cand
            break
    if delta_col is None:
        non_id_cols = [c for c in dp.columns if c not in ["ai_app_id","name","application","year"]]
        if not non_id_cols:
            raise ValueError("delta_progress.csv is missing a value column (e.g., 'delta_p').")
        delta_col = non_id_cols[0]
    dp[delta_col] = pd.to_numeric(dp[delta_col], errors="coerce").fillna(0.0)

    years_sorted = sorted(dp["year"].unique().tolist())
    if target_year is None:
        target_year = years_sorted[-1]

    # Compute Δ and cumulative per year
    records = []
    for y in years_sorted:
        m = dp[dp["year"]==y].dropna(subset=["ai_app_id"])
        vec = pd.Series(0.0, index=app_index, dtype=float)
        m2 = m.set_index("ai_app_id")[delta_col]
        inter = vec.index.intersection(m2.index)
        vec.loc[inter] = pd.to_numeric(m2.loc[inter], errors="coerce").fillna(0.0).values

        delta_e = E.values.dot(vec.values)
        delta_daioe = np.square(delta_e)
        for idx, occ in enumerate(occ_index):
            records.append({"occ": occ, "year": y, "delta_e": float(delta_e[idx]), "delta_DAIOE": float(delta_daioe[idx])})

    ts = pd.DataFrame(records).sort_values(["year","occ"])

    # Cumulative level (Eq. 6)
    ts["DAIOE_cum"] = ts.groupby("occ", group_keys=False)["delta_DAIOE"].cumsum()

    # Percentiles (by year) for the cumulative level
    def pct_rank_grouped(df, value_col):
        def pct_rank(x):
            n = len(x)
            return 100.0 * (x.rank(method="average") - 1) / (n - 1) if n>1 else 100.0
        return df.groupby("year", group_keys=False).apply(lambda g: g.assign(pctl_cum= pct_rank(g[value_col])))

    ts = pct_rank_grouped(ts, "DAIOE_cum")

    out_timeseries_csv.parent.mkdir(parents=True, exist_ok=True)
    ts.to_csv(out_timeseries_csv, index=False)

    # Snapshot for target_year
    snap = ts[ts["year"]==target_year].copy()
    snap = snap.rename(columns={
        "delta_e": f"delta_e_{target_year}",
        "delta_DAIOE": f"delta_DAIOE_{target_year}",
        "DAIOE_cum": f"DAIOE_{target_year}",
        "pctl_cum": f"pctl_{target_year}"
    })
    snap = snap.drop(columns=["year"])
    snap.to_csv(out_snapshot_csv, index=False)

    return snap, ts

# === Summaries ===
def write_summary(merged_csv: Path, out_json: Path, top_k: int = 20) -> None:
    df = pd.read_csv(merged_csv)
    def safe_corr(x: str, y: str):
        cols = [c for c in (x, y) if c in df.columns]
        if len(cols) < 2: 
            return None
        d = df[[x, y]].dropna()
        if d.shape[0] <= 2:
            return None
        return float(np.corrcoef(d[x], d[y])[0,1])

    title_col = "occ_title_onetsoc2010" if "occ_title_onetsoc2010" in df.columns else None

    def pick_cols(frame, keys):
        cols = ["occ"]
        if title_col:
            cols.append(title_col)
        if isinstance(keys, (list, tuple)):
            cols.extend(keys)
        else:
            cols.append(keys)
        return frame[cols]

    # Detect dynamic Eq.(3) column
    new_col = next((c for c in df.columns if c.startswith("pctl_new_")), None)
    # Detect cumulative percentile column (from Eq. 6 snapshot)
    cum_col = next((c for c in df.columns if c.startswith("pctl_") and c != "pctl_A" and c != "pctl_B" and not c.startswith("pctl_new_")), None)

    top_new = pick_cols(df.sort_values(new_col, ascending=False).head(top_k), new_col).to_dict(orient="records") if new_col else []
    bottom_new = pick_cols(df.sort_values(new_col, ascending=True).head(top_k), new_col).to_dict(orient="records") if new_col else []

    top_cum = pick_cols(df.sort_values(cum_col, ascending=False).head(top_k), cum_col).to_dict(orient="records") if cum_col else []
    bottom_cum = pick_cols(df.sort_values(cum_col, ascending=True).head(top_k), cum_col).to_dict(orient="records") if cum_col else []

    if "pctl_rank_allapps" in df.columns:
        inc = dec = inc_cum = dec_cum = []
        if new_col:
            delta = df.copy()
            delta["delta_new_minus_old"] = delta[new_col] - delta["pctl_rank_allapps"]
            inc = pick_cols(delta.sort_values("delta_new_minus_old", ascending=False).head(top_k),
                            ["pctl_rank_allapps","delta_new_minus_old"]).to_dict(orient="records")
            dec = pick_cols(delta.sort_values("delta_new_minus_old", ascending=True).head(top_k),
                            ["pctl_rank_allapps","delta_new_minus_old"]).to_dict(orient="records")
        if cum_col:
            delta2 = df.copy()
            delta2["delta_cum_minus_old"] = delta2[cum_col] - delta2["pctl_rank_allapps"]
            inc_cum = pick_cols(delta2.sort_values("delta_cum_minus_old", ascending=False).head(top_k),
                                ["pctl_rank_allapps","delta_cum_minus_old"]).to_dict(orient="records")
            dec_cum = pick_cols(delta2.sort_values("delta_cum_minus_old", ascending=True).head(top_k),
                                ["pctl_rank_allapps","delta_cum_minus_old"]).to_dict(orient="records")
    else:
        inc = dec = inc_cum = dec_cum = [], [], [], []

    summary = {
        "n_occupations": int(df.shape[0]),
        "correlations": {
            "pctl_A_vs_DAIOE": safe_corr("pctl_A", "pctl_rank_allapps"),
            "pctl_B_vs_DAIOE": safe_corr("pctl_B", "pctl_rank_allapps"),
            "pctl_new_vs_DAIOE": (safe_corr(new_col, "pctl_rank_allapps") if new_col else None),
            "pctl_level_vs_DAIOE": (safe_corr(cum_col, "pctl_rank_allapps") if cum_col else None),
        },
        "top_by_pctl_new": top_new,
        "bottom_by_pctl_new": bottom_new,
        "top_by_pctl_level": top_cum,
        "bottom_by_pctl_level": bottom_cum,
        "largest_increases_new_minus_old": inc,
        "largest_decreases_new_minus_old": dec,
        "largest_increases_level_minus_old": inc_cum,
        "largest_decreases_level_minus_old": dec_cum,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print("Saved summary JSON:", out_json)

def write_summary_tables(merged_csv: Path, out_csv: Path, top_k: int = 20) -> None:
    df = pd.read_csv(merged_csv)
    title_col = "occ_title_onetsoc2010" if "occ_title_onetsoc2010" in df.columns else None

    # def base_cols(frame, cols):
    #    cols_out = ["occ"]
    #    if title_col: cols_out.append(title_col)
    #    cols_out += cols
    #    return frame[cols_out]
    def base_cols(frame, cols):
        cols_out = ["occ"]
        if title_col and title_col in frame.columns:
            cols_out.append(title_col)
    # keep only columns that actually exist, and drop duplicates while preserving order
        cols_out += [c for c in cols if c in frame.columns]
        cols_out = list(dict.fromkeys(cols_out))
        return frame.loc[:, cols_out]

    parts = []

    new_col = next((c for c in df.columns if c.startswith("pctl_new_")), None)
    if new_col:
        top_new = base_cols(df.sort_values(new_col, ascending=False).head(top_k), [new_col]); top_new.insert(0, "section", "top_new_eq3"); parts.append(top_new)
        bottom_new = base_cols(df.sort_values(new_col, ascending=True).head(top_k), [new_col]); bottom_new.insert(0, "section", "bottom_new_eq3"); parts.append(bottom_new)
        if "pctl_rank_allapps" in df.columns:
            delta = df.copy(); delta["delta_new_minus_old"] = delta[new_col] - delta["pctl_rank_allapps"]
            inc = base_cols(delta.sort_values("delta_new_minus_old", ascending=False).head(top_k), [new_col, "pctl_rank_allapps", "delta_new_minus_old"]); inc.insert(0, "section", "largest_increases_eq3"); parts.append(inc)
            dec = base_cols(delta.sort_values("delta_new_minus_old", ascending=True).head(top_k), [new_col, "pctl_rank_allapps", "delta_new_minus_old"]); dec.insert(0, "section", "largest_decreases_eq3"); parts.append(dec)

    cum_col = next((c for c in df.columns if c.startswith("pctl_") and c != "pctl_A" and c != "pctl_B" and not c.startswith("pctl_new_")), None)
    if cum_col:
        top_cum = base_cols(df.sort_values(cum_col, ascending=False).head(top_k), [cum_col]); top_cum.insert(0, "section", "top_level_eq6"); parts.append(top_cum)
        bottom_cum = base_cols(df.sort_values(cum_col, ascending=True).head(top_k), [cum_col]); bottom_cum.insert(0, "section", "bottom_level_eq6"); parts.append(bottom_cum)
        if "pctl_rank_allapps" in df.columns:
            delta2 = df.copy(); delta2["delta_level_minus_old"] = delta2[cum_col] - delta2["pctl_rank_allapps"]
            inc2 = base_cols(delta2.sort_values("delta_level_minus_old", ascending=False).head(top_k), [cum_col, "pctl_rank_allapps", "delta_level_minus_old"]); inc2.insert(0, "section", "largest_increases_eq6"); parts.append(inc2)
            dec2 = base_cols(delta2.sort_values("delta_level_minus_old", ascending=True).head(top_k), [cum_col, "pctl_rank_allapps", "delta_level_minus_old"]); dec2.insert(0, "section", "largest_decreases_eq6"); parts.append(dec2)

    out = pd.concat(parts, axis=0, ignore_index=True) if parts else pd.DataFrame()
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)
    print("Saved summary tables CSV:", out_csv)

def main():
    # MAIN: The only function you need to run.
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--vantage", default=DEFAULT_VANTAGE)
    ap.add_argument("--model_primary", default=os.environ.get("MODEL_PRIMARY",""))
    ap.add_argument("--model_secondary", default=os.environ.get("MODEL_SECONDARY",""))
    ap.add_argument("--gamma", type=float, default=1.0)
    ap.add_argument("--delta", type=float, default=2.0)
    ap.add_argument("--year", type=int, default=None, help="Target year for Eq.(3) using annual delta progress")
    ap.add_argument("--skip-estimate", action="store_true",
                help="Skip estimate_mapping.py and reuse output/mapping_matrix_9x58_v<V>.csv if it exists")
    args = ap.parse_args()

    _print_header("STEP 0: Standardize applications")
    apps = standardize_applications(APPS_CSV)
    print(apps.head())

    _print_header("STEP 1: Generate anchors from FRS (max/min per ability)")
    anchors = generate_anchors_from_frs(apps, ABILITIES_CSV, FRS_COMBINED_XLSX, ANCHORS_CSV)
    print(f"Saved anchors: {ANCHORS_CSV} ({anchors.shape[0]} rows)")

    _print_header("STEP 2: Estimate 9x58 mapping (LLM-based)")
    mapping_existing = OUT / f"mapping_matrix_9x58_v{args.vantage}.csv"

    if args.skip_estimate and mapping_existing.exists():
        mapping_path = mapping_existing
        print("Skipping estimate_mapping.py; reusing", mapping_path)
    else:
        try:
            mapping_path = run_estimate_mapping(
                args.vantage,
                model_primary=args.model_primary,
                model_secondary=args.model_secondary
            )
            print("Mapping matrix:", mapping_path)
        except Exception as e:
            print("WARNING: estimate_mapping.py failed:", e)
            if mapping_existing.exists():
                mapping_path = mapping_existing
                print("Proceeding with existing mapping file:", mapping_path)
            else:
                raise
    _print_header("STEP 3: Validate against FRS 2018")
    try:
        comp_path = run_validate_against_frs(args.vantage)
        print("Validation comparison (our vs FRS):", comp_path)
    except Exception as e:
        print("WARNING: validate_against_frs.py failed:", e)

    _print_header("STEP 4: Build occupation ability weights (58) from O*NET Excel")
    occ_w_path = RAW/"occ_ability_weights.csv"
    W = build_occ_ability_weights(ABILITIES_XLSX, SKILLS_XLSX, ABILITIES_CSV, occ_w_path)
    print("Saved occupation ability weights:", occ_w_path, "shape:", W.shape)

    _print_header("STEP 5: Compute exposures (A: no social downweight; B: DAIOE-style) and compare to DAIOE")
    final_out = OUT/"final_exposure_comparison.csv"
    comp = compute_exposures_and_compare(mapping_path, occ_w_path, DAIOE_TSV, final_out, gamma=args.gamma, delta=args.delta)
    print("Saved final comparison:", final_out)
    print(comp.head(10).to_string(index=False))

    _print_header("STEP 6: ΔDAIOE (Eq.3, robustness variant) from annual Δp")
    if not DELTA_LONG_CSV.exists():
        tmpl = apps[["ai_app_id","name"]].copy()
        tmpl["year"] = 2023
        tmpl["delta_p"] = 0.0
        DELTA_LONG_CSV.parent.mkdir(parents=True, exist_ok=True)
        tmpl.to_csv(DELTA_LONG_CSV, index=False)
        print(f"Template created for annual progress: {DELTA_LONG_CSV}")

    new_daioe_tmp = OUT/"_tmp_new_daioe.csv"
    new_daioe_df, used_year = compute_new_daioe_from_progress(mapping_path, occ_w_path, DELTA_LONG_CSV, new_daioe_tmp, target_year=args.year)
    new_daioe_path = OUT/f"new_daioe_{used_year}.csv"
    new_daioe_df.to_csv(new_daioe_path, index=False)
    print(f"Saved ΔDAIOE (Eq.3) for {used_year}:", new_daioe_path)

    # Merge Eq.(3) into comparison
    merged_out = OUT/"final_exposure_comparison_with_new_daioe.csv"
    comp2 = pd.read_csv(final_out).merge(new_daioe_df, on="occ", how="left")
    new_col = next((c for c in comp2.columns if c.startswith("pctl_new_")), None)
    if "pctl_rank_allapps" in comp2.columns and new_col in comp2.columns and comp2.shape[0]>2:
        comp2["corr_new_vs_old"] = np.corrcoef(comp2[new_col], comp2["pctl_rank_allapps"])[0,1]
    comp2.to_csv(merged_out, index=False)
    print("Saved merged comparison (incl. ΔDAIOE):", merged_out)

    _print_header("STEP 7: Level DAIOE (Eq.6) = sum of yearly ΔDAIOE (built from annual Δp)")
    new_daioe_level_single = OUT / f"new_daioe_cumulative_{used_year}.csv"
    new_daioe_level_ts = OUT/"new_daioe_timeseries.csv"
    snap, ts = compute_daioe_level_timeseries(mapping_path, occ_w_path, DELTA_LONG_CSV, new_daioe_level_single, new_daioe_level_ts, target_year=used_year)
    print("Saved DAIOE level snapshot:", new_daioe_level_single)
    print("Saved DAIOE Δ/level time series:", new_daioe_level_ts)

    # Merge level snapshot into comparison
    comp3 = pd.read_csv(merged_out).merge(snap, on="occ", how="left")
    cum_pctl_col = next((c for c in comp3.columns if c.startswith("pctl_") and c not in ("pctl_A","pctl_B") and not c.startswith("pctl_new_")), None)
    if "pctl_rank_allapps" in comp3.columns and cum_pctl_col in comp3.columns and comp3.shape[0]>2:
        comp3["corr_level_vs_old"] = np.corrcoef(comp3[cum_pctl_col], comp3["pctl_rank_allapps"])[0,1]
    merged_out2 = OUT/"final_exposure_comparison_with_new_and_cumulative_daioe.csv"
    comp3.to_csv(merged_out2, index=False)
    print("Saved merged comparison (incl. ΔDAIOE + Level DAIOE):", merged_out2)

    # Summaries
    summary_json = OUT/"summary.json"
    write_summary(Path(merged_out2), summary_json, top_k=20)
    summary_tables_csv = OUT/"summary_tables.csv"
    write_summary_tables(Path(merged_out2), summary_tables_csv, top_k=20)

if __name__ == "__main__":
    main()
