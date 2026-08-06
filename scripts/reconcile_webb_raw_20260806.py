"""Reconcile the delivered raw Webb file against the vintage that built the reference.

THE PROBLEM. `1_data_ore/webb_indices_soc2010.dta` (dated 2021-07-09) and
`2_data_enriched/webb_indices_soc2010.dta` disagree on `robot_score` for exactly
eight occupations, by a factor of exactly 4.0 on every one. They agree to the bit
on `ai_score` and `software_score`, and the published reference panels follow the
enriched values.

WHY THAT SETTLES WHICH IS RIGHT. Erik's raw-to-intermediate step for Webb is a
pure rename and a dropped column, nothing else:

    use "${raw_data}/webb_indices_soc2010.dta", clear
        rename SOC2010code occ_code_soc
        foreach var in agg_pairs ai_score software_score robot_score {
            rename `var' webb19_`var'
        }
        drop webb19_agg_pairs

No division, no rescaling, here or anywhere else in his code. So the enriched
file's values ARE the raw file's values, for whichever raw vintage produced it.
Since they differ, the raw copy in the 27 May share is not the copy that built the
reference in the same share. The delivery is internally inconsistent on this one
variable, and the enriched side is the one consistent with everything published.

WHAT THIS SCRIPT DOES. Writes a reconciled raw-shaped file: the delivered raw,
with `robot_score` taken from the enriched vintage. Schema, column order, row
order and every other value are preserved, so the only difference from the
delivered raw is the eight values that are demonstrably stale.

WHAT IT DOES NOT DO. It does not touch `ai_score` or `software_score`, which
already agree exactly, and it does not invent a correction: every replacement
value is read from a file Erik delivered.

Run with the pinned venv:
    ./.venv/bin/python scripts/reconcile_webb_raw_20260806.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daioe import io  # noqa: E402

RAW = ROOT / "data/raw/webb_indices_soc2010.dta"
ENR = ROOT / "data/enriched_ref/webb_indices_soc2010.dta"
OUT = ROOT / "data/derived/webb_indices_soc2010_reconciled.dta"


def main() -> None:
    raw = io.read_dta(str(RAW))
    enr = io.read_dta(str(ENR))
    print(f"raw      {raw.shape}  {list(raw.columns)}")
    print(f"enriched {enr.shape}  {list(enr.columns)}")

    raw["_k"] = raw["SOC2010code"].astype(str).str.strip()
    enr["_k"] = enr["occ_code_soc"].astype(str).str.strip()
    if set(raw["_k"]) != set(enr["_k"]):
        print("FATAL: the two files do not cover the same occupations.")
        sys.exit(1)

    m = raw.merge(enr, on="_k", how="left", validate="one_to_one")

    # the two columns that must already agree; assert rather than assume
    for a, b in [("ai_score", "webb19_ai_score"),
                 ("software_score", "webb19_software_score")]:
        d = (m[a] - m[b]).abs().max()
        print(f"  {a:<16} max|diff| vs enriched = {d:.3e}")
        if d > 1e-9:
            print(f"FATAL: {a} disagrees too. This is not the documented case; stop.")
            sys.exit(2)

    d = (m["robot_score"] - m["webb19_robot_score"]).abs()
    changed = m.loc[d > 1e-9, ["_k", "robot_score", "webb19_robot_score"]].copy()
    changed["ratio"] = changed["robot_score"] / changed["webb19_robot_score"]
    print(f"\n  robot_score differs on {len(changed)} occupations")
    print(changed.to_string(index=False, float_format=lambda x: f"{x:.6f}"))
    if len(changed) and not changed["ratio"].round(6).eq(4.0).all():
        print("\nFATAL: the ratio is no longer exactly 4.0 on every row. The premise of")
        print("this reconciliation was that single systematic factor; re-diagnose.")
        sys.exit(3)
    print("\n  ratio is exactly 4.0 on every differing row, as documented")

    out = raw.drop(columns=["_k"]).copy()
    out["robot_score"] = m["webb19_robot_score"].to_numpy()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_stata(str(OUT), write_index=False, version=118)
    print(f"\n  wrote {OUT.relative_to(ROOT)}  {out.shape}")
    print("  columns and order preserved:", list(out.columns))


if __name__ == "__main__":
    main()
