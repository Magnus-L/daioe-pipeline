"""
build_anchors_v2.py — per-application calibration anchors from FRS 2018, balanced across all twelve.

Why this exists
---------------
The published anchors (`raw_data/anchors.csv`, built by `master_pipeline.generate_anchors_from_frs`)
take, for each ability, the single application FRS scored highest and the single one it scored
lowest. `estimate_mapping.py` then regroups those *by application* and shows each application the
first five of each. The consequence is severe imbalance, because an application only receives an
anchor when it happens to be a global extreme:

    app 1 Abstract strategy games   17 high / 17 low
    app 4 Visual question answering  1 high /  0 low
    app 7 Language modeling          7 high /  0 low
    apps 10-12 (the new subdomains)  0 high /  0 low

Applications were therefore not scored by the same instrument, and the three new subdomains would
have been scored with no calibration at all. That is the defect this file removes.

The change
----------
For each application we take its own top-k and bottom-k abilities *from its own FRS row*. Same
source (FRS 2018 "Combined"), same idea (show the model where this application sits at the extremes
of the scale), but k high and k low for every application by construction, including the new ones.

Why the new subdomains need no hand-written anchors
---------------------------------------------------
FRS 2018 scored sixteen applications, not nine. DAIOE used nine of them. Three of the seven it left
behind are the concepts we are now adding, so their anchors are derived exactly as the others are
rather than invented:

    10 Agentic task execution    <- "solving real-world technical problems"          (approximate)
    11 Maths/science reasoning   <- "solving constrained, well-specified technical problems" (close)
    12 Software engineering      <- "generating computer programs from specifications"       (close)

Only the agentic mapping is a real judgement call: FRS 2018 had no conception of tool use, browsing
or long-horizon autonomy, so "solving real-world technical problems" is the nearest available
concept rather than the same one. That is recorded in `applications_v2.csv:frs_match` and is the
one cell that wants a human decision.

Held-out cells
--------------
Every (application, ability) pair named as an anchor is written to `mod_data/anchor_cells_v2.csv`.
Those cells are shown to the model with their FRS value attached, so they cannot honestly be used to
validate against FRS. The validator excludes them. This is also why the published 0.7762 figure is a
reproduction statistic rather than an out-of-sample one: roughly a fifth of the cells it scores were
named, with their FRS value, in the prompt that produced them.

Outputs
-------
    raw_data/anchors_v2.csv       ai_app_id, ability_id, label, frs_score, note
    mod_data/anchor_cells_v2.csv  ai_app_id, ability_id     (the held-out set)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw_data"
MOD = ROOT / "mod_data"
MOD.mkdir(exist_ok=True)

# FRS covers abilities 1-52. Abilities 53-58 are the six social skills added for this project and
# have no FRS counterpart, so no anchor is ever drawn from them. Scores for 53-58 are therefore
# model judgements calibrated only by the 52 O*NET anchors, which matters because those six rows
# are what would replace the social-skills discount in the 2024 vintage.
FRS_ABILITY_MAX = 52


def load_frs(frs_xlsx: Path, abilities: pd.DataFrame) -> pd.DataFrame:
    """Return FRS 'Combined' in long form: frs_row, ability_id, score."""
    combined = pd.read_excel(frs_xlsx, sheet_name="Combined")
    name_to_id = {
        str(r["ability_name"]).strip().lower(): int(r["ability_id"])
        for _, r in abilities.iterrows()
        if int(r["ability_id"]) <= FRS_ABILITY_MAX
    }
    col_to_id = {
        c: name_to_id[str(c).strip().lower()]
        for c in combined.columns
        if str(c).strip().lower() in name_to_id
    }
    missing = set(name_to_id.values()) - set(col_to_id.values())
    if missing:
        raise ValueError(f"FRS sheet is missing ability ids {sorted(missing)}; alias table is stale")

    rows = []
    for _, row in combined.iterrows():
        frs_row = str(row["abilities"]).strip().lower()
        for col, ability_id in col_to_id.items():
            if pd.notnull(row[col]):
                rows.append({"frs_row": frs_row, "ability_id": ability_id, "score": float(row[col])})
    return pd.DataFrame(rows)


def _pick(g: pd.DataFrame, k: int, high: bool) -> pd.DataFrame:
    """Take k anchors from one FRS row, spreading picks across tied scores.

    Ties matter more than they look. Most FRS rows carry a long run of 0.00, and those zeros are
    contiguous in ability_id because O*NET orders abilities by domain (cognitive, then psychomotor,
    then physical, then sensory). Breaking ties by id therefore hands the model five zeros drawn
    from a single domain, so it sees what "no support" looks like in the sensory corner and nowhere
    else. Sampling evenly within each tied group instead spreads the zeros across domains, which is
    what makes them useful as calibration.
    """
    ordered = g.sort_values(["score", "ability_id"], ascending=[not high, True])
    chosen: list[pd.DataFrame] = []
    need = k
    for _, tied in ordered.groupby("score", sort=False):
        if need <= 0:
            break
        tied = tied.sort_values("ability_id")
        if len(tied) <= need:
            chosen.append(tied)
            need -= len(tied)
        else:
            idx = np.unique(np.linspace(0, len(tied) - 1, need).round().astype(int))
            chosen.append(tied.iloc[idx])
            need -= len(idx)
    return pd.concat(chosen).head(k)


def build(apps: pd.DataFrame, abilities: pd.DataFrame, frs_long: pd.DataFrame, k: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    ability_meta = abilities.set_index("ability_id")
    anchor_rows, held_out = [], []

    for _, app in apps.iterrows():
        app_id, frs_row = int(app["ai_app_id"]), str(app["frs_row"]).strip().lower()
        g = frs_long[frs_long["frs_row"] == frs_row]
        if g.empty:
            raise ValueError(
                f"application {app_id} ({app['name']}) declares frs_row {frs_row!r}, which is not a "
                f"row of the FRS Combined sheet. Available: {sorted(frs_long['frs_row'].unique())}"
            )

        picks = [("high", _pick(g, k, high=True)), ("low", _pick(g, k, high=False))]

        for label, chunk in picks:
            for _, r in chunk.iterrows():
                ability_id = int(r["ability_id"])
                meta = ability_meta.loc[ability_id]
                name, definition = meta["ability_name"], str(meta["ability_definition"]).rstrip(".").lower()
                verb = "engages" if label == "high" else "does little for"
                note = (
                    f"[{app['name']}] {verb} '{name}' ({definition}). FRS 2018 scores this pair "
                    f"{r['score']:.2f}."
                )
                anchor_rows.append({
                    "ai_app_id": app_id, "ability_id": ability_id, "label": label,
                    "frs_score": float(r["score"]), "note": note,
                })
                held_out.append({"ai_app_id": app_id, "ability_id": ability_id})

    return pd.DataFrame(anchor_rows), pd.DataFrame(held_out).drop_duplicates()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apps", default=str(RAW / "applications_v2.csv"))
    # k=8 built, 5 shown per replicate. The surplus is what the replicate rotation consumes: each
    # replicate calibrates on a different window of the same eight, so the spread across replicates
    # measures sensitivity to the choice of exemplar. All eight are held out of validation, since
    # across three replicates seven of the eight are shown at least once.
    ap.add_argument("--k", type=int, default=8, help="anchors per application per direction")
    args = ap.parse_args()

    apps = pd.read_csv(args.apps)
    abilities = pd.read_csv(RAW / "abilities.csv")
    frs_long = load_frs(RAW / "mapping_matrix.xlsx", abilities)

    anchors, held_out = build(apps, abilities, frs_long, args.k)
    anchors.to_csv(RAW / "anchors_v2.csv", index=False)
    held_out.to_csv(MOD / "anchor_cells_v2.csv", index=False)

    counts = anchors.groupby(["ai_app_id", "label"]).size().unstack(fill_value=0)
    counts.index = [f"{i:>2} {n}" for i, n in zip(apps.ai_app_id, apps.name)]
    print(counts.to_string())
    print(f"\nanchors: {len(anchors)}  held-out cells: {len(held_out)} of {len(apps) * FRS_ABILITY_MAX}")
    print(f"validation cells remaining (FRS abilities only): {len(apps) * FRS_ABILITY_MAX - len(held_out)}")
    print(f"\nwrote {RAW / 'anchors_v2.csv'}\nwrote {MOD / 'anchor_cells_v2.csv'}")


if __name__ == "__main__":
    main()
