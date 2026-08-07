"""
validate_mapping_v2.py — score any candidate mapping matrix against the FRS 2018 expert matrix.

This is the acceptance test. Because FRS scored the same applications by hand, every open design
choice (model, effort level, replicate count, anchor scheme, whether to score all twelve at once)
can be settled by which one agrees best with the expert matrix, rather than by argument.

The honest number and the comparable number
-------------------------------------------
The prompt shows the model a handful of that application's own FRS scores as calibration. Those
cells cannot then be used to validate against FRS: the answer was in the question. So two figures
are reported for every run,

    all_cells   every application x ability pair FRS covers. Comparable with the published 0.7762
                in Online Appendix J, and inflated the same way that figure is.
    held_out    the same, with anchored cells removed. This is the one to quote.

Applied to the published matrix, the gap between the two says how much of the appendix's validation
statistic was calibration leaking into its own test.

Alignment
---------
`applications_v2.csv` carries an explicit `frs_row` for each application, so alignment is declared
rather than guessed by alias table. FRS covers abilities 1-52; the six social skills (53-58) have no
expert counterpart and are excluded from every figure here. That exclusion is worth remembering,
because those six rows are exactly what would replace the social-skills discount in the 2024
vintage, and nothing in this validation speaks to them.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, MOD, OUT = ROOT / "raw_data", ROOT / "mod_data", ROOT / "output"

FRS_ABILITY_MAX = 52


def frs_long(apps: pd.DataFrame, abilities: pd.DataFrame) -> pd.DataFrame:
    combined = pd.read_excel(RAW / "mapping_matrix.xlsx", sheet_name="Combined")
    name_to_id = {
        str(r["ability_name"]).strip().lower(): int(r["ability_id"])
        for _, r in abilities.iterrows() if int(r["ability_id"]) <= FRS_ABILITY_MAX
    }
    col_to_id = {c: name_to_id[str(c).strip().lower()] for c in combined.columns
                 if str(c).strip().lower() in name_to_id}
    combined["_row"] = combined["abilities"].astype(str).str.strip().str.lower()
    frs_by_row = combined.set_index("_row")

    rows = []
    for _, app in apps.iterrows():
        key = str(app["frs_row"]).strip().lower()
        if key not in frs_by_row.index:
            continue                                   # application has no FRS counterpart
        r = frs_by_row.loc[key]
        for col, ability_id in col_to_id.items():
            if pd.notnull(r[col]):
                rows.append({"ai_app_id": int(app["ai_app_id"]), "ability_id": ability_id,
                             "frs": float(r[col])})
    return pd.DataFrame(rows)


def legacy_anchor_cells(anchors_csv: Path, show: int = 5) -> pd.DataFrame:
    """Reconstruct which cells the *published* run actually showed the model.

    `estimate_mapping.py` grouped anchors by application and took `["high"][:5]` and `["low"][:5]`
    in file order, so the shown set is the first `show` of each label per application, not the whole
    anchor table. Reconstructed here so the published matrix can be judged on the same held-out
    basis as a new run.
    """
    a = pd.read_csv(anchors_csv)
    keep = []
    for app_id, sub in a.groupby("ai_app_id"):
        for label in ("high", "low"):
            keep.append(sub[sub.label.str.lower() == label].head(show))
    out = pd.concat(keep)[["ai_app_id", "ability_id"]].dropna()
    return out.astype(int).drop_duplicates()


def stats(df: pd.DataFrame) -> dict:
    if len(df) < 3:
        return {"n": int(len(df))}
    return {
        "n": int(len(df)),
        "pearson": round(float(df.ours.corr(df.frs)), 4),
        "spearman": round(float(df.ours.corr(df.frs, method="spearman")), 4),
        "mae": round(float((df.ours - df.frs).abs().mean()), 4),
        "bias": round(float((df.ours - df.frs).mean()), 4),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--matrix", required=True, help="candidate matrix csv, applications x abilities")
    ap.add_argument("--apps", default=str(RAW / "applications_v2.csv"))
    ap.add_argument("--held-out", default=str(MOD / "anchor_cells_v2.csv"),
                    help="cells to exclude; use --legacy-anchors for the published matrix")
    ap.add_argument("--legacy-anchors", action="store_true",
                    help="reconstruct the shown-anchor set from the original anchors.csv")
    ap.add_argument("--label", default="", help="name for the report file")
    args = ap.parse_args()

    apps = pd.read_csv(args.apps)
    abilities = pd.read_csv(RAW / "abilities.csv")

    mat = pd.read_csv(args.matrix, index_col=0)
    mat.columns = [int(c) for c in mat.columns]
    ours = mat.stack().reset_index()
    ours.columns = ["ai_app_id", "ability_id", "ours"]
    ours = ours[ours.ability_id <= FRS_ABILITY_MAX]

    comp = ours.merge(frs_long(apps, abilities), on=["ai_app_id", "ability_id"], how="inner").dropna()
    if comp.empty:
        raise SystemExit("no overlap with FRS; check that --apps declares the right frs_row values")

    excl = legacy_anchor_cells(RAW / "anchors.csv") if args.legacy_anchors else pd.read_csv(args.held_out)
    excl = set(map(tuple, excl[["ai_app_id", "ability_id"]].astype(int).values))
    comp["anchored"] = [(a, b) in excl for a, b in zip(comp.ai_app_id, comp.ability_id)]
    held = comp[~comp.anchored]

    name = dict(zip(apps.ai_app_id, apps.name))
    per_app = []
    for app_id, g in held.groupby("ai_app_id"):
        per_app.append({"ai_app_id": int(app_id), "name": name.get(app_id, "?"), **stats(g)})

    report = {
        "matrix": str(args.matrix),
        "applications_compared": int(comp.ai_app_id.nunique()),
        "all_cells": stats(comp),
        "held_out": stats(held),
        "anchored_cells_excluded": int(comp.anchored.sum()),
        "per_application_held_out": sorted(per_app, key=lambda d: d["ai_app_id"]),
    }

    label = args.label or Path(args.matrix).stem
    (OUT / f"frs_validation_{label}.json").write_text(json.dumps(report, indent=2))

    print(f"matrix: {args.matrix}")
    print(f"  all cells   n={report['all_cells']['n']:>4}  pearson={report['all_cells']['pearson']:.4f}  "
          f"spearman={report['all_cells']['spearman']:.4f}  mae={report['all_cells']['mae']:.4f}")
    print(f"  held out    n={report['held_out']['n']:>4}  pearson={report['held_out']['pearson']:.4f}  "
          f"spearman={report['held_out']['spearman']:.4f}  mae={report['held_out']['mae']:.4f}")
    print(f"  (excluded {report['anchored_cells_excluded']} anchored cells)\n")
    print(f"  {'application':<40} {'n':>4} {'pearson':>8} {'mae':>7}")
    for d in report["per_application_held_out"]:
        print(f"  {d['name']:<40} {d['n']:>4} {d.get('pearson', float('nan')):>8.3f} {d.get('mae', float('nan')):>7.3f}")
    print(f"\nwrote {OUT / f'frs_validation_{label}.json'}")


if __name__ == "__main__":
    main()
