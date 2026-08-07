#!/usr/bin/env python3

# %% 
"""
standardize_and_validate_frs.py

Syfte:
- Länka ihop din 9×58-matris (mapping_matrix_9x58_v2018.csv) med applications.csv
  för att få app-namn.
- Länka ihop FRS Combined-matrisen (mapping_matrix.xlsx, sheet 'Combined') med
  abilities.csv för att översätta FRS-kolumnnamn (t.ex. 'oral comprehension')
  till O*NET ability_id (1..52) och därmed till dina kolumner '1'..'52'.
- Standardisera namn (Image comprehension -> Visual question answering, Generating images -> Image generation, etc.).
- Beräkna korrelation/MAE mellan din 9×58-matris och FRS, baserat på de appar och abilities
  som överlappar.
- Skriva ut:
  * en CSV med dina 9 rader + app-namn
  * en LaTeX-rapport
  * en JSON-sammanfattning
"""

import argparse
import sys
import json
import difflib
import re
from pathlib import Path

import pandas as pd
import numpy as np


# ---------- Hjälpfunktioner ----------

def standardize_name(s: str):
    """Normalisera app-namn till FRS-terminologi (case-insensitive)."""
    if not isinstance(s, str):
        return s
    s0 = s.strip()

    # Normalisera konstiga bindestreck till ett vanligt hyphen
    s0 = (s0
          .replace("\u2011", "-")
          .replace("\u2010", "-")
          .replace("\u2013", "-")
          .replace("\u2014", "-"))

    rules = [
        (r"^image\s*comprehension$", "Visual question answering"),
        (r"^visual\s*question\s*answer(ing)?$", "Visual question answering"),
        (r"^generat(ing|ive)\s*images?$", "Image generation"),
        (r"^image\s*generation$", "Image generation"),
        (r"^language\s*model(ing|ling)$", "Language modelling"),  # UK-stavning som i FRS
        (r"^real[\s-]*time\s*video\s*games$", "Real-time video games"),
        (r"^speech\s*recognition$", "Speech recognition"),
        (r"^image\s*recognition$", "Image recognition"),
        (r"^reading\s*comprehension$", "Reading comprehension"),
        (r"^translation$", "Translation"),
        (r"^abstract\s*strategy\s*games$", "Abstract strategy games"),
    ]

    out = s0
    low = s0.lower()
    for pat, repl in rules:
        if re.match(pat, low, flags=re.IGNORECASE):
            out = repl
            break

    # Städa upp whitespace och extra dash-varianter
    out = re.sub(r"\s+", " ", out).strip()
    out = out.replace("–", "-").replace("—", "-")
    return out


def pearson_corr(a, b) -> float:
    a = np.asarray(a).ravel()
    b = np.asarray(b).ravel()
    if a.size < 2 or b.size < 2 or np.std(a) == 0 or np.std(b) == 0:
        return np.nan
    return float(np.corrcoef(a, b)[0, 1])


def mae(a, b) -> float:
    a = np.asarray(a).ravel()
    b = np.asarray(b).ravel()
    if a.size == 0 or b.size == 0:
        return np.nan
    return float(np.mean(np.abs(a - b)))


# ---------- Huvudlogik ----------

def main():
    ap = argparse.ArgumentParser(
        description="Standardize app names and validate our 9x58 mapping against FRS Combined."
    )
    ap.add_argument(
        "--our_csv", required=True,
        help="Vår 9×58-matris (mapping_matrix_9x58_v2018.csv) med 'ai_app_id' + kolumner '1'..'58'."
    )
    ap.add_argument(
        "--apps_csv", required=True,
        help="applications.csv med kolumnerna 'id' och 'name'."
    )
    ap.add_argument(
        "--abilities_csv", required=True,
        help="abilities.csv med 'ability_id' och 'ability_name'."
    )
    ap.add_argument(
        "--frs_xlsx",
        help="FRS mapping_matrix.xlsx (där Combined-sheeter finns)."
    )
    ap.add_argument(
        "--frs_sheet", default="Combined",
        help="Namn på FRS-sheet (default: Combined)."
    )
    ap.add_argument(
        "--frs_csv",
        help="CSV-export av FRS Combined (används om --frs_xlsx inte ges)."
    )
    ap.add_argument(
        "--out_csv", required=True,
        help="Fil att skriva ut vår 9×58 med app-namn (standardiserade) till."
    )
    ap.add_argument(
        "--report_tex", required=True,
        help="Fil att skriva LaTeX-rapporten till."
    )

    args = ap.parse_args()

    our_csv = Path(args.our_csv)
    apps_csv = Path(args.apps_csv)
    abilities_csv = Path(args.abilities_csv)

    if not our_csv.exists():
        sys.exit(f"[ERROR] Our CSV not found: {our_csv}")
    if not apps_csv.exists():
        sys.exit(f"[ERROR] apps_csv not found: {apps_csv}")
    if not abilities_csv.exists():
        sys.exit(f"[ERROR] abilities_csv not found: {abilities_csv}")

    # --- 1. Läs in vår 9×58 och koppla på app-namn från applications.csv ---
    our = pd.read_csv(our_csv)
    apps = pd.read_csv(apps_csv)

    if "ai_app_id" not in our.columns:
        sys.exit("[ERROR] 'ai_app_id' column missing in our mapping.")

    # Försök hitta ID- och namnkolumn i applications.csv med flera möjliga namn
    id_col = None
    name_col = None

    for cand in ["id", "Id", "ID", "app_id", "ai_app_id"]:
        if cand in apps.columns:
            id_col = cand
            break

    for cand in ["name", "Name", "application", "Application", "AI application", "AI Application"]:
        if cand in apps.columns:
            name_col = cand
            break

    if id_col is None or name_col is None:
        print("Columns in apps_csv:", list(apps.columns), file=sys.stderr)
        sys.exit(
        "[ERROR] Could not detect ID/name columns in apps_csv. "
        "Expected something like 'id' + 'name' or 'application'."
    )

    # Gör merge med rätt ID-kolumn
    our_m = our.merge(apps, left_on="ai_app_id", right_on=id_col, how="left")

    if our_m[name_col].isna().any():
        print("[WARN] Some ai_app_id values have no matching name in applications.csv", file=sys.stderr)

    # Spara även ett enhetligt kolumnnamn 'name' för bekvämlighet
    our_m["name"] = our_m[name_col].astype(str)

    # Standardisera våra app-namn
    our_m["app_std"] = our_m["name"].astype(str).apply(standardize_name)


    # --- 2. Läs in FRS Combined ---
    if args.frs_xlsx:
        frs_source = Path(args.frs_xlsx)
        if not frs_source.exists():
            sys.exit(f"[ERROR] frs_xlsx not found: {frs_source}")
        frs = pd.read_excel(frs_source, sheet_name=args.frs_sheet)
    elif args.frs_csv:
        frs_source = Path(args.frs_csv)
        if not frs_source.exists():
            sys.exit(f"[ERROR] frs_csv not found: {frs_source}")
        frs = pd.read_csv(frs_source)
    else:
        sys.exit("[ERROR] Provide either --frs_xlsx or --frs_csv.")

    # FRS-appnamn ligger i kolumnen 'abilities' på Combined, men vi gör en liten detektering
    frs_app_col = None
    for cand in ["abilities", "Application", "application", "App", "Name"]:
        if cand in frs.columns:
            frs_app_col = cand
            break
    if frs_app_col is None:
        sys.exit("[ERROR] Could not detect the FRS application name column (e.g. 'abilities').")

    frs["app_std"] = frs[frs_app_col].astype(str).apply(standardize_name)

    # --- 3. Läs in ability-tabellen och bygg namn->ID-karta ---
    abil = pd.read_csv(abilities_csv)
    if not {"ability_id", "ability_name"}.issubset(abil.columns):
        sys.exit("[ERROR] abilities_csv must contain 'ability_id' and 'ability_name' columns.")

    abil_map = {
        str(row["ability_name"]).strip().lower(): int(row["ability_id"])
        for _, row in abil.iterrows()
    }

    # --- 4. Identifiera FRS ability-kolumner och mappa dem till våra '1'..'58' ---
    frs_ability_cols = [
        c for c in frs.columns
        if c not in [frs_app_col, "ability_id"] and pd.api.types.is_numeric_dtype(frs[c])
    ]

    pairs = []              # (our_col_name, frs_col_name, ability_id)
    unmatched_frs_cols = [] # FRS ability-kolumner som inte hittas i abilities.csv
    missing_in_our = []     # ability_id som finns i abilities.csv men inte som kolumn i vår 9×58

    for col in frs_ability_cols:
        key = str(col).strip().lower()
        if key in abil_map:
            aid = abil_map[key]
            our_col = str(aid)  # vår kolumn i 9×58
            if our_col in our.columns:
                pairs.append((our_col, col, aid))
            else:
                missing_in_our.append((aid, col))
        else:
            unmatched_frs_cols.append(col)

    if not pairs:
        sys.exit("[ERROR] No ability overlap between our numeric 1..58 and FRS named columns. "
                 "Check that abilities.csv matches the FRS ability names.")

    ability_cols_our = [p[0] for p in pairs]
    ability_cols_frs = [p[1] for p in pairs]
    ability_ids_used = [p[2] for p in pairs]

    # --- 5. Överlapp i applikationer (standardiserade namn) ---
    our_names = set(our_m["app_std"].dropna().str.strip())
    frs_names = set(frs["app_std"].dropna().str.strip())
    overlap = sorted(our_names & frs_names)
    missing_after = sorted(our_names - frs_names)

    def best_match(name):
        return difflib.get_close_matches(name, list(frs_names), n=1, cutoff=0.6)[0] if frs_names else None

    fuzzy = {nm: best_match(nm) for nm in missing_after}

    # --- 6. Beräkna valideringsmått (endast overlappande appar) ---
    corr_flat = np.nan
    mae_flat = np.nan
    n_rows = 0

    if overlap:
        our_rows = []
        frs_rows = []
        for nm in overlap:
            r_our = our_m.loc[our_m["app_std"] == nm, ability_cols_our]
            r_frs = frs.loc[frs["app_std"] == nm, ability_cols_frs]
            if len(r_our) == 0 or len(r_frs) == 0:
                continue
            v_our = r_our.mean(axis=0).values.astype(float)
            v_frs = r_frs.mean(axis=0).values.astype(float)
            our_rows.append(v_our)
            frs_rows.append(v_frs)
        if our_rows and frs_rows:
            A = np.vstack(our_rows)
            B = np.vstack(frs_rows)
            corr_flat = pearson_corr(A.flatten(), B.flatten())
            mae_flat = mae(A.flatten(), B.flatten())
            n_rows = A.shape[0]

    # --- 7. Skriv ut standardiserad CSV (med namn) ---
    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    our_m.to_csv(out_csv, index=False)

    # --- 8. Bygg LaTeX-rapport ---
    ability_idxs_str = ", ".join(map(str, sorted(set(ability_ids_used))))
    no_match_rows = (
        " (none) & (n/a) \\\\"
        if not fuzzy
        else " \\\\\n".join([f"{k} & {v if v else '-'}" for k, v in fuzzy.items()])
    )
    corr_str = "NA" if np.isnan(corr_flat) else f"{corr_flat:.3f}"
    mae_str = "NA" if np.isnan(mae_flat) else f"{mae_flat:.3f}"

    tex_template = r"""\documentclass[11pt]{article}
\usepackage[a4paper,margin=1in]{geometry}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{siunitx}
\usepackage{hyperref}
\hypersetup{colorlinks=true,linkcolor=blue,urlcolor=blue}

\title{FRS-style Mapping Validation and Name Standardization}
\author{AI-Econ Lab (pipeline output)}
\date{\today}

\begin{document}
\maketitle

\section*{Objective}
We standardize application names in our 9$\times$58 mapping to match the terminology used by Felten, Raj, and Seamans (2018), then validate the mapping against the FRS ``Combined'' sheet by aligning overlapping application names and ability columns.

\section*{Inputs}
\begin{itemize}
  \item Our mapping: \texttt{%(our_csv)s}
  \item FRS matrix: \texttt{%(frs_source)s} (sheet: \texttt{%(frs_sheet)s})
  \item Applications: \texttt{%(apps_csv)s}
  \item Abilities: \texttt{%(abilities_csv)s}
  \item Standardized output: \texttt{%(out_csv)s}
\end{itemize}

\section*{Overlap Summary (Applications)}
\begin{tabular}{@{}ll@{}}
\toprule
Unique standardized names in our 9 apps & %(n_our_names)d \\
Unique standardized names in FRS sheet & %(n_frs_names)d \\
Overlap (exact standardized) & %(n_overlap)d \\
Overlapping ability IDs (by mapping) & %(ability_idxs_str)s \\
\bottomrule
\end{tabular}

\subsection*{Names with No Exact Match After Standardization (with suggestions)}
\begin{longtable}{@{}ll@{}}
\toprule
Our (standardized) & Suggested FRS name \\
\midrule
\endhead
%(no_match_rows)s
\bottomrule
\end{longtable}

\section*{Ability Alignment}
We map each FRS ability column (e.g.\ \emph{oral comprehension}) to an O*NET ability ID using \texttt{abilities.csv} and then to the corresponding numeric column (1--58) in our 9$\times$58 matrix.

\begin{itemize}
  \item FRS numeric ability columns considered: %(n_frs_ability_cols)d
  \item Matched to our numeric ability columns: %(n_matched_ability_cols)d
  \item FRS ability columns with no match in abilities.csv: %(n_unmatched_frs_cols)d
  \item FRS ability columns whose O*NET ID was not present among our 1--58 columns: %(n_missing_in_our)d
\end{itemize}

\section*{Validation Metrics (Overlapping Apps Only)}
\begin{tabular}{@{}lll@{}}
\toprule
Rows aligned (apps) & Pearson corr (flattened) & MAE (flattened) \\
\midrule
%(n_rows)d & %(corr_str)s & %(mae_str)s \\
\bottomrule
\end{tabular}

\section*{Interpretation}
If overlap is high and the correlation is strong with reasonable MAE, our mapping is consistent with the FRS Combined matrix after terminology alignment. Any remaining non-overlaps typically reflect residual naming differences, different application sets, or abilities outside the 1--52 core shared between the two representations.

\end{document}
"""

    tex = tex_template % {
        "our_csv": str(our_csv),
        "frs_source": str(frs_source),
        "frs_sheet": args.frs_sheet,
        "apps_csv": str(apps_csv),
        "abilities_csv": str(abilities_csv),
        "out_csv": str(out_csv),
        "n_our_names": len(our_names),
        "n_frs_names": len(frs_names),
        "n_overlap": len(overlap),
        "ability_idxs_str": ability_idxs_str,
        "no_match_rows": no_match_rows,
        "n_frs_ability_cols": len(frs_ability_cols),
        "n_matched_ability_cols": len(ability_cols_our),
        "n_unmatched_frs_cols": len(unmatched_frs_cols),
        "n_missing_in_our": len(missing_in_our),
        "n_rows": n_rows,
        "corr_str": corr_str,
        "mae_str": mae_str,
    }

    tex_path = Path(args.report_tex)
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    tex_path.write_text(tex, encoding="utf-8")

    # --- 9. JSON-sammanfattning ---
    summary = {
        "our_csv": str(our_csv),
        "apps_csv": str(apps_csv),
        "abilities_csv": str(abilities_csv),
        "frs_source": str(frs_source),
        "frs_sheet": args.frs_sheet,
        "out_csv": str(out_csv),
        "overlap_apps": overlap,
        "missing_apps_with_suggestion": {k: (v if v else None) for k, v in fuzzy.items()},
        "ability_cols_our": ability_cols_our,
        "ability_cols_frs": ability_cols_frs,
        "ability_ids_used": ability_ids_used,
        "unmatched_frs_ability_cols": unmatched_frs_cols,
        "missing_in_our_abilities": missing_in_our,
        "aligned_rows": int(n_rows),
        "pearson_corr_flat": None if np.isnan(corr_flat) else float(corr_flat),
        "mae_flat": None if np.isnan(mae_flat) else float(mae_flat),
    }

    tex_path.with_suffix(".json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("[OK] Wrote standardized CSV:", out_csv)
    print("[OK] Wrote LaTeX report:", tex_path)
    print("[OK] Wrote JSON summary:", tex_path.with_suffix(".json"))
    if not overlap:
        print("[WARN] No overlapping applications after standardization. "
              "Check naming and mapping rules.")
    else:
        print(f"[INFO] Overlap after standardization: {len(overlap)} apps; aligned rows used: {n_rows}")
        if not np.isnan(corr_flat):
            print(f"[INFO] Pearson corr (flattened): {corr_flat:.3f}; MAE: {mae_flat:.3f}")


if __name__ == "__main__":
    main()
