"""Derive a SOC2010 -> SOC2018 crosswalk and audit it against the DAIOE SOC panel.

WHY THIS SCRIPT EXISTS
----------------------
config.yaml has carried a commented-out ``soc2018`` taxonomy entry since Phase 3 with
the note "crosswalk present in repo". It is not present, and never was: ``data/raw/``
holds crosswalks for ISCO08, SSYK2012 and SSYK96 only. The README and the 19 July
decision note repeat the same claim. This script closes that gap.

SOURCE
------
BLS blocks this environment outright (HTTP 403 on both the file and the page), but
O*NET republishes the same crosswalk inside ``OccupationalListings.zip``:

    https://www.onetcenter.org/dl_files/OccupationalListings.zip
      -> OccupationalListings/Crosswalks/2010_to_2018_SOC_Crosswalk.xlsx

That file keys on the **O*NET-SOC 2010** code (8-digit, e.g. ``11-1011.03``), not the
SOC2010 code the pipeline's SOC panel uses. The 6-digit prefix of an O*NET-SOC 2010
code IS its SOC 2010 code by construction of the O*NET-SOC taxonomy, so the SOC-level
crosswalk derives by taking that prefix and deduplicating (SOC2010, SOC2018) pairs.

That derivation is the one modelling step here, and it is worth stating plainly: we are
inferring a SOC-to-SOC mapping from an O*NET-SOC-to-SOC one. Where several O*NET-SOC
detailed occupations under one SOC2010 code map to different SOC2018 codes, the
deduplicated result is a genuine one-to-many split and is reported as such below rather
than resolved silently.

WHAT IT DOES NOT DO
-------------------
It does not wire the taxonomy into ``config.yaml`` and it does not run stage 5. The
aggregation rule for split and merged occupations is Magnus's and Erik's call, and the
inventory this prints is the input to that call.

Output: data/derived/soc2010_to_soc2018.dta (+ .csv) and a printed audit.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
SOC_PANEL = ROOT / "data" / "out" / "daioe_panel_soc.dta"

XLSX_MEMBER = "OccupationalListings/Crosswalks/2010_to_2018_SOC_Crosswalk.xlsx"


def load_crosswalk(src: Path) -> pd.DataFrame:
    """Read the O*NET workbook, whether given as the .zip or the extracted .xlsx."""
    if src.suffix == ".zip":
        with zipfile.ZipFile(src) as z:
            with z.open(XLSX_MEMBER) as fh:
                raw = pd.read_excel(fh, header=None)
    else:
        raw = pd.read_excel(src, header=None)

    # The sheet carries three title rows before the header row; find it rather than
    # hard-coding an offset, so a reformatted release fails loudly instead of silently
    # shifting every column by one.
    hdr = None
    for i in range(min(12, len(raw))):
        row = raw.iloc[i].astype(str).str.strip()
        if row.str.contains("O\\*NET-SOC 2010 Code", regex=True).any():
            hdr = i
            break
    if hdr is None:
        raise SystemExit("could not find the header row; the O*NET file layout changed")

    df = raw.iloc[hdr + 1:].copy()
    df.columns = raw.iloc[hdr].astype(str).str.strip().tolist()
    df = df.rename(columns={
        "O*NET-SOC 2010 Code": "onetsoc2010",
        "O*NET-SOC 2010 Title": "onetsoc2010_title",
        "2018 SOC Code": "SOC2018code",
        "2018 SOC Title": "SOC2018title",
    })
    df = df[["onetsoc2010", "SOC2018code", "SOC2018title"]].dropna(subset=["onetsoc2010"])
    for c in df.columns:
        df[c] = df[c].astype(str).str.strip()
    return df


def derive_soc_level(df: pd.DataFrame) -> pd.DataFrame:
    """O*NET-SOC 2010 (8-digit) -> SOC2010 (6-digit prefix), then dedupe the pairs."""
    out = df.copy()
    out["SOC2010code"] = out["onetsoc2010"].str.split(".").str[0]
    bad = out.loc[~out["SOC2010code"].str.match(r"^\d{2}-\d{4}$"), "SOC2010code"].unique()
    if len(bad):
        raise SystemExit(f"unexpected SOC2010 code format: {bad[:5]}")
    out = (out[["SOC2010code", "SOC2018code", "SOC2018title"]]
           .drop_duplicates()
           .sort_values(["SOC2010code", "SOC2018code"])
           .reset_index(drop=True))
    return out


def audit(cw: pd.DataFrame, panel_codes: set[str] | None,
          panel_codes_with_data: set[str] | None = None) -> None:
    n2010 = cw["SOC2010code"].nunique()
    n2018 = cw["SOC2018code"].nunique()
    print(f"\n=== crosswalk ===\n  pairs {len(cw)}   SOC2010 codes {n2010}   SOC2018 codes {n2018}")

    fan_out = cw.groupby("SOC2010code")["SOC2018code"].nunique()
    fan_in = cw.groupby("SOC2018code")["SOC2010code"].nunique()

    splits = fan_out[fan_out > 1]
    merges = fan_in[fan_in > 1]
    # A pair is clean 1:1 only if BOTH sides are unique: its SOC2010 maps to one SOC2018
    # AND that SOC2018 draws on no other SOC2010. Only those carry the round-trip
    # invariant (the SOC2018 DAIOE value must equal the SOC2010 one exactly).
    clean = cw[cw["SOC2010code"].map(fan_out).eq(1) & cw["SOC2018code"].map(fan_in).eq(1)]

    print("\n=== structure ===")
    print(f"  clean 1:1 pairs (round-trip invariant applies)  {len(clean)}")
    print(f"  SOC2010 codes that SPLIT across SOC2018         {len(splits)}")
    print(f"  SOC2018 codes that MERGE several SOC2010        {len(merges)}")

    if len(splits):
        print("\n  splits (SOC2010 -> n SOC2018), largest first:")
        for code, n in splits.sort_values(ascending=False).head(12).items():
            tgt = ", ".join(sorted(cw.loc[cw["SOC2010code"] == code, "SOC2018code"]))
            print(f"    {code} -> {n}: {tgt}")
    if len(merges):
        print("\n  merges (SOC2018 <- n SOC2010), largest first:")
        for code, n in merges.sort_values(ascending=False).head(12).items():
            src = ", ".join(sorted(cw.loc[cw["SOC2018code"] == code, "SOC2010code"]))
            print(f"    {code} <- {n}: {src}")

    if panel_codes is None:
        print("\n=== coverage ===\n  SOC panel not readable; coverage not audited")
        return

    mapped = panel_codes & set(cw["SOC2010code"])
    orphan = panel_codes - set(cw["SOC2010code"])
    print("\n=== coverage against the DAIOE SOC2010 panel ===")
    print(f"  panel SOC2010 codes            {len(panel_codes)}")
    print(f"  with a SOC2018 mapping         {len(mapped)}")
    print(f"  ORPHANED (no mapping)          {len(orphan)}")
    if orphan:
        print("    " + ", ".join(sorted(orphan)[:20]) + (" ..." if len(orphan) > 20 else ""))

    # SOC2018 codes that no panel occupation feeds at all.
    reachable = set(cw.loc[cw["SOC2010code"].isin(panel_codes), "SOC2018code"])
    unreachable = set(cw["SOC2018code"]) - reachable
    print(f"  SOC2018 codes with NO panel source at all {len(unreachable)}")
    if unreachable:
        print("    " + ", ".join(sorted(unreachable)))

    # The number that actually matters, and it is smaller. A SOC2010 code can sit in the
    # panel and still carry no exposure: stage 5 keeps 68 SOC occupations "for
    # transparency" with year missing and exp_cumul_allapps = 0. Those contribute no
    # dated row, so their SOC2018 successors collapse to nothing. Counting merely
    # "reachable" codes overstates coverage by exactly that set.
    if panel_codes_with_data is not None:
        dated = set(cw.loc[cw["SOC2010code"].isin(panel_codes_with_data), "SOC2018code"])
        print(f"\n  SOC2018 codes that RECEIVE A DATED VALUE  {len(dated)} of {n2018}")
        print(f"  SOC2018 codes left EMPTY                  {len(set(cw['SOC2018code']) - dated)}")
        print("    of which, no panel source at all:        "
              f"{len(unreachable)}")
        print("    of which, source present but undated:    "
              f"{len(set(cw['SOC2018code']) - dated - unreachable)}")

    print("\n  NOTE: counts only. Employment-weighted coverage needs BLS OES, which is")
    print("  403-blocked from this environment; it is a separate fetch before release.")


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/OccupationalListings.zip")
    if not src.exists():
        raise SystemExit(f"source not found: {src}\n  download OccupationalListings.zip "
                         f"from onetcenter.org/dl_files/ and pass its path")

    cw = derive_soc_level(load_crosswalk(src))

    panel_codes = panel_dated = None
    if SOC_PANEL.exists():
        panel = pd.read_stata(SOC_PANEL)
        codes = panel["occ_code_soc"].astype(str).str.strip()
        panel_codes = set(codes)
        panel_dated = set(codes[panel["year"].notna()])

    audit(cw, panel_codes, panel_dated)

    DERIVED.mkdir(parents=True, exist_ok=True)
    cw.to_csv(DERIVED / "soc2010_to_soc2018.csv", index=False)
    cw.to_stata(DERIVED / "soc2010_to_soc2018.dta", write_index=False, version=118)
    print(f"\nwrote {DERIVED/'soc2010_to_soc2018.dta'}  ({len(cw)} pairs)")
    print("NOT wired into config.yaml: stage 5 resolves crosswalks under data/raw/,")
    print("which is a symlink into Erik's delivered source tree. Where a derived file")
    print("should live is a decision, not a default.")


if __name__ == "__main__":
    main()
