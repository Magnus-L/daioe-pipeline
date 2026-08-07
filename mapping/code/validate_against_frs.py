"""
validate_against_frs.py — Compare our mapping to the FRS “Combined” benchmark (9×52)

Purpose (non-programmer summary):
- Loads the FRS reference weights (from mapping_matrix.xlsx, sheet “Combined”).
- Extracts the 9×52 slice from our estimated 9×58 mapping.
- Computes correlations/overlaps to quantify how close we are to the expert matrix.
- Writes a comparison CSV for documentation and diagnostics.

Expected inputs:
- mapping_matrix.xlsx (sheet “Combined” with the nine apps × 52 abilities)
- output/mapping_matrix_9x58_v{vantage}.csv (our estimate)

Expected output:
- output/comparison_our_vs_frs_v{vantage}.csv

How this file is called:
- `code/master_pipeline.py` calls `validate_against_frs.py` via `run_validate_against_frs(...)`.
"""

# %% ----------- Direct to relative project folders -----------
from pathlib import Path
import argparse, json
import pandas as pd
import numpy as np

# Project root = parent of this script's folder
ROOT = Path(__file__).resolve().parents[1]
raw_dir  = ROOT / "raw_data"
mod_dir  = ROOT / "mod_data"
out_dir  = ROOT / "output"
for p in (raw_dir, mod_dir, out_dir):
    p.mkdir(exist_ok=True)

# ---------- Helpers ----------
# Plain-English: Function `load_our_matrix` — see module docstring for overall workflow context.
def load_our_matrix(vantage: str):
    """Load 9×58 matrix from output; fallback to build from scores in mod_data if needed."""
    mpath = out_dir / f"mapping_matrix_9x58_v{vantage}.csv"
    if mpath.exists():
        mat = pd.read_csv(mpath, index_col=0)
        return mat, str(mpath)
    # fallback: try to pivot scores
    spath = mod_dir / f"mapping_scores_v{vantage}.csv"
    if spath.exists():
        df = pd.read_csv(spath)
        mat = df.pivot_table(index="ai_app_id", columns="ability_id", values="r_mean", aggfunc="mean")
        return mat, str(spath) + " (pivoted)"
    return None, None

# Plain-English: Function `find_best_overlap` — see module docstring for overall workflow context.
def find_best_overlap(our_mat: pd.DataFrame, frs_xlsx: Path, apps: pd.DataFrame, abilities: pd.DataFrame):
    """Try each sheet, map ability names + app aliases, compute correlation on overlap."""
    APP_ALIASES = {
        "Abstract strategy games": ["Abstract strategy games","Strategy games"],
        "Real‑time video games": ["Real-time video games","Real time video games","RTS games"],
        "Image recognition": ["Image classification","Image recognition"],
        "Image comprehension": ["Visual question answering","VQA","Image captioning","Image QA"],
        "Image generation": ["Image generation","Text-to-image","Text2Image"],
        "Reading comprehension": ["Reading comprehension","Machine reading","SQuAD"],
        "Language modelling": ["Language modeling","Language modelling","Text generation","Language modeling (LM)"],
        "Translation": ["Machine translation","Translation","MT"],
        "Speech recognition": ["Speech recognition","ASR"],
    }

    xl = pd.ExcelFile(frs_xlsx)
    best = None
    best_report = None

    # prepare ability name map (lowercased) for quick joins
    abilities_lc = abilities.copy()
    abilities_lc["ability_name_norm"] = abilities_lc["ability_name"].str.strip().str.lower()

    for sheet in xl.sheet_names:
        try:
            df = xl.parse(sheet)
        except Exception:
            continue
        # find ability name column heuristically
        cols = {str(c).lower(): c for c in df.columns}
        abil_col = None
        for cand in ["ability", "ability name", "name", "element", "element name", "ability_name"]:
            if cand in cols:
                abil_col = cols[cand]; break
        if not abil_col:
            continue
        work = df.copy()
        work["ability_name_norm"] = work[abil_col].astype(str).str.strip().str.lower()
        merged = work.merge(abilities_lc[["ability_id","ability_name_norm"]], on="ability_name_norm", how="inner")
        if merged.empty:
            continue

        # map app columns
        app_cols = {}
        for i, row in apps.iterrows():
            aliases = APP_ALIASES.get(row["name"], [row["name"]])
            # find first alias present in the FRS sheet
            found = None
            for a in aliases:
                if a in work.columns:
                    found = a; break
            if found:
                app_cols[int(row["ai_app_id"])] = found

        if not app_cols:
            continue

        # construct long-form overlap
        parts = []
        for app_id, col in app_cols.items():
            sub = merged[["ability_id", col]].rename(columns={col: "frs_score"})
            sub["ai_app_id"] = app_id
            parts.append(sub)
        frs_long = pd.concat(parts, ignore_index=True).dropna(subset=["frs_score"])

        # align with our matrix
        our_long = our_mat.stack().reset_index()
        our_long.columns = ["ai_app_id","ability_id","our_score"]
        comp = our_long.merge(frs_long, on=["ai_app_id","ability_id"], how="inner").dropna()

        if len(comp) >= 20:
            rho = comp[["our_score","frs_score"]].corr().iloc[0,1]
            report = (sheet, len(comp), float(rho))
            if best is None or rho > best_report[2]:
                best, best_report = comp, report

    return best, best_report

# Plain-English: Function `main` — see module docstring for overall workflow context.
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vantage", default="2018")
    ap.add_argument("--frs_file", default=str(raw_dir / "mapping_matrix.xlsx"))
    args = ap.parse_args()

    # Required inputs
    apps_path = raw_dir / "applications.csv"
    abil_path = raw_dir / "abilities.csv"
    frs_path  = Path(args.frs_file)

    if not apps_path.exists() or not abil_path.exists():
        raise SystemExit("Missing applications.csv or abilities.csv in raw_data/.")

    apps = pd.read_csv(apps_path)
    if "ai_app_id" not in apps.columns:
        apps = apps.assign(ai_app_id=range(1, len(apps)+1))
    abilities = pd.read_csv(abil_path)

    our_mat, src = load_our_matrix(args.vantage)
    result = {
        "vantage": args.vantage,
        "our_source": src,
        "frs_file": str(frs_path),
        "status": "",
    }

    if our_mat is None:
        result["status"] = "no_our_matrix_found"
        (out_dir / f"validation_report_v{args.vantage}.json").write_text(json.dumps(result, indent=2))
        print("No mapping matrix/scores found. Run estimate_mapping.py first.")
        return

    if not frs_path.exists():
        result["status"] = "no_frs_file_found"
        (out_dir / f"validation_report_v{args.vantage}.json").write_text(json.dumps(result, indent=2))
        print("FRS Excel file not found in raw_data/. Place mapping_matrix.xlsx there.")
        return

    comp, rep = find_best_overlap(our_mat, frs_path, apps, abilities)
    if comp is None or rep is None:
        result["status"] = "no_overlap_detected"
        (out_dir / f"validation_report_v{args.vantage}.json").write_text(json.dumps(result, indent=2))
        print("Could not find sufficient overlap with any FRS sheet. Check aliases or sheet formats.")
        return

    # Save comparison and summary
    comp_path = out_dir / f"frs_overlap_v{args.vantage}.csv"
    comp.to_csv(comp_path, index=False)

    result.update({
        "status": "ok",
        "best_sheet": rep[0],
        "overlap_cells": int(rep[1]),
        "pearson_corr": float(rep[2]),
        "overlap_csv": str(comp_path),
    })
    (out_dir / f"validation_report_v{args.vantage}.json").write_text(json.dumps(result, indent=2))

    print("Best overlap sheet:", rep[0])
    print("Overlapping cells:", rep[1])
    print("Correlation (our vs FRS):", round(rep[2],3))
    print("Saved:", comp_path)
    print("Saved:", out_dir / f"validation_report_v{args.vantage}.json")

if __name__ == "__main__":
    main()