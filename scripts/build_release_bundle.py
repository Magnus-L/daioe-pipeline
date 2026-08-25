#!/usr/bin/env python3
"""Assemble the DAIOE scores bundle for the Zenodo record.

The scores are not in git, so publishing the repository does not publish them. This
builds the archive that carries them, with everything a user needs to know which object
they are holding.

Each vintage goes in its own top-level folder. That is the whole point: the frozen
2010-2023 index behind the published estimates and the 2024 refresh are different
objects, and mixing them silently changes published numbers.

v1.0.0 ships the frozen index and the 2024 refresh only. The 2025-onward vintage is
held back for v1.1.0; see the note on VINTAGES below.

Usage:  python scripts/build_release_bundle.py 1.0.0
Output: dist/daioe-v<version>-scores.zip
"""
from pathlib import Path
import hashlib
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = sys.argv[1] if len(sys.argv) > 1 else "1.0.0"
STAGE = ROOT / "dist" / f"daioe-v{VERSION}-scores"
ZIP = ROOT / "dist" / f"daioe-v{VERSION}-scores.zip"

# (folder in the bundle, source directory, one-line description)
VINTAGES = [
    ("frozen-2010-2023",
     ROOT / "data" / "reference" / "Publication",
     "The index behind the published estimates. Use this to replicate."),
    ("refresh-2024",
     # 25 Aug 2026 (audit F6): the July snapshot recomputed the published window
     # (the Track A workbook's recovered 2016-2023 rows moved 47k frozen cells) and
     # was replaced by the seam-disciplined rebuild: frozen 2010-2023 verbatim,
     # 2024 chained at the seam, gates green. The old snapshot folder is kept on
     # disk for provenance but must never ship.
     ROOT / "data" / "vintage" / "refresh2024_seam_20260825" / "out" / "Publication",
     "The 2024 annual refresh: frozen 2010-2023 verbatim, 2024 chained at the seam."),
    # HELD BACK FROM v1.0.0 (decision, 10 Aug 2026). The 2025-onward vintage ships as
    # v1.1.0 once the co-authors have signed off on it. Its three documented caveats
    # (SWE-bench Verified's 2025 increment is an upper bound on a single 2024
    # evaluation; five of nine original applications have no living 2025 source;
    # ceiling-type anchors await a uniform convention) make it the object most likely
    # to change, and a published Zenodo record cannot be withdrawn. Zenodo versioning
    # exists for exactly this: the concept DOI will resolve to v1.1.0 when it lands.
    # ("vintage-2025",
    #  ROOT / "data" / "vintage" / "vintage_2025_20260808" / "out" / "Publication",
    #  "The 2025-onward vintage."),
]

# Built on request and not in Publication format; shipped so it is not lost.
EXTRAS = [
    # data/out's copy spans 2010-2023, the frozen window, so it belongs in v1.0.0.
    # The copy inside the 2025 vintage folder runs to 2025 and is held back with it.
    ("soc2018/daioe_panel_soc2018.dta",
     ROOT / "data" / "out" / "daioe_panel_soc2018.dta",
     "SOC 2018 build on the frozen 2010-2023 window; panel export, not Publication format."),
]

DOCS = [
    (ROOT / "LICENSE-DATA", "LICENSE-DATA"),
    (ROOT / "VINTAGES.md", "VINTAGES.md"),
    (ROOT / "data" / "derived" / "errata_frozen_workbook_v1.csv",
     "errata_frozen_workbook_v1.csv"),
    (ROOT / "data" / "derived" / "human_anchors_v1.csv", "human_anchors_v1.csv"),
    (ROOT / "data" / "derived" / "pwc_provenance.csv", "provenance/pwc_provenance.csv"),
    (ROOT / "data" / "derived" / "pwc_provenance_README.md", "provenance/README.md"),
]


def repo_commit() -> str:
    import subprocess
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True).stdout.strip()
    except Exception:
        return "unknown"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_sha256(root: Path) -> str:
    """Deterministic content hash of a directory tree: relative path + per-file
    SHA-256, in sorted order. Identifies the recovered archive snapshot."""
    h = hashlib.sha256()
    for f in sorted(root.rglob("*")):
        if f.is_file():
            h.update(str(f.relative_to(root)).encode())
            h.update(sha256(f).encode())
    return h.hexdigest()


def data_dictionary(stage: Path) -> None:
    """Machine- and human-readable schema of every table in the bundle, generated
    from the staged files themselves so it cannot drift from what ships."""
    import json
    import pandas as pd
    d = {"_conventions": {
        "missing": "empty cells are missing values, never zeros",
        "tsv_delimiter": "\\t",
        "unique_key": "asserted on the staged file; null means the file is not "
                      "keyed on (occupation code, year)"}}
    for dta in sorted(stage.rglob("*.dta")):
        df = pd.read_stata(dta)
        rel = str(dta.relative_to(stage))
        key = None
        if "year" in df.columns:
            occ = [c for c in df.columns
                   if c.startswith(("occ_code", "ssyk", "SOC", "ISCO"))][:1]
            if occ and not df.duplicated(subset=occ + ["year"]).any():
                key = occ + ["year"]
        entry = {"rows": int(len(df)), "unique_key": key,
                 "columns": {c: str(df[c].dtype) for c in df.columns}}
        if "year" in df.columns:
            entry["years"] = [int(df["year"].min()), int(df["year"].max())]
        d[rel] = entry
    (stage / "DATA_DICTIONARY.json").write_text(json.dumps(d, indent=1),
                                                encoding="utf-8")
    lines = ["# Data dictionary (generated from the staged files at build time)",
             "", "Empty cells are missing values, never zeros. `.tsv` files are",
             "tab-separated. The `.csv`-free naming is deliberate.", ""]
    for rel, e in d.items():
        if rel.startswith("_"):
            continue
        lines.append(f"## `{rel}`")
        lines.append(f"- rows: {e['rows']}; years: {e.get('years')}; "
                     f"unique key: {e['unique_key']}")
        lines.append("- columns: " + ", ".join(f"`{c}` ({t})"
                     for c, t in e["columns"].items()))
        lines.append("")
    (stage / "DATA_DICTIONARY.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"  DATA_DICTIONARY: {sum(1 for k in d if not k.startswith('_'))} tables")


def main():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    present = []
    for name, src, desc in VINTAGES:
        if not src.exists():
            print(f"  SKIP {name}: {src} absent")
            continue
        dst = STAGE / name
        dst.mkdir(parents=True)
        n = 0
        for f in sorted(src.iterdir()):
            if f.is_file() and not f.name.startswith("."):
                # The tab-separated text exports carry a .csv suffix internally
                # (Stata-era convention); the published artifact names them .tsv
                # (decision Magnus, 25 Aug 2026, cross-vendor finding 16).
                name = f.name[:-4] + ".tsv" if f.suffix == ".csv" else f.name
                shutil.copy2(f, dst / name)
                n += 1
        present.append((name, desc, n))
        print(f"  {name}: {n} files")

    for rel, src, desc in EXTRAS:
        if src.exists():
            dst = STAGE / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            present.append((rel.split("/")[0], desc, 1))
            print(f"  {rel}: 1 file")

    for src, rel in DOCS:
        if src.exists():
            dst = STAGE / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    data_dictionary(STAGE)

    # Archive-snapshot identification appended to the staged provenance README
    # (the source file is untouched): the recovered PwC archive has no DOI, so a
    # deterministic tree hash is the identifier a permanent record can carry.
    arch = ROOT / "data" / "updates" / "pwc-archive"
    if arch.exists():
        n = sum(1 for f in arch.rglob("*") if f.is_file())
        prov = STAGE / "provenance" / "README.md"
        prov.parent.mkdir(parents=True, exist_ok=True)
        with open(prov, "a", encoding="utf-8") as fh:
            fh.write(
                "\n\n## Archive snapshot identification\n\n"
                "The recovered Papers with Code archive behind the refresh and "
                "later vintages has no DOI; it is identified by a deterministic "
                "content hash over the archive tree (sorted relative path + "
                f"per-file SHA-256): `{tree_sha256(arch)}` ({n} files).\n")
        print("  provenance: archive snapshot hash appended")

    (STAGE / "README.md").write_text(readme(present), encoding="utf-8")

    lines = []
    for f in sorted(STAGE.rglob("*")):
        if f.is_file() and f.name != "SHA256SUMS":
            lines.append(f"{sha256(f)}  {f.relative_to(STAGE)}")
    (STAGE / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if ZIP.exists():
        ZIP.unlink()
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(STAGE.rglob("*")):
            if f.is_file():
                z.write(f, Path(STAGE.name) / f.relative_to(STAGE))

    print(f"\n{ZIP.relative_to(ROOT)}  ({ZIP.stat().st_size/1e6:.1f} MB, "
          f"{len(lines)} files, checksummed)")


def readme(present):
    rows = "\n".join(f"| `{n}/` | {d} |" for n, d, _ in present)
    return f"""# DAIOE — Dynamic AI Occupational Exposure, scores v{VERSION}

Occupation-year AI exposure scores, built from measured performance gains on public AI
benchmarks and O*NET occupational ability profiles.

Code, documentation and the construction pipeline:
https://github.com/Magnus-L/daioe-pipeline — this bundle was built at commit
`{repo_commit()}`. The pipeline reproduces every substantive `daioe_*` cell from raw
inputs; the legacy percentile columns are reproduced from this deposited artifact
itself (see "Percentile ranks and ties" below and `VINTAGES.md`).

## The folders are different objects

| folder | what it is |
|---|---|
{rows}

**They are not interchangeable.** The frozen index underlies the published estimates
and is the replication object. The 2024 refresh carries the frozen 2010-2023 window
cell-for-cell identically at stored precision and appends 2024, chained on the frozen
2023 level; its 2024 rows are new and do not appear in any published estimate. Cite
the vintage you used.

The 2025-onward vintage is not in this release. It exists, but several of its
properties are still provisional, so it ships separately as v1.1.0 rather than being
frozen into a permanent record before it settles. `VINTAGES.md` in this bundle
documents all vintages and marks that section as forthcoming.

## Known errors and intended use

The frozen series knowingly retains four small transcription discrepancies against
the original benchmark repositories, documented with evidence in
`errata_frozen_workbook_v1.csv` in this bundle. They are retained by design: the
frozen folder replicates the paper, exactly. The 2024 refresh carries the same frozen
2010-2023 levels, so neither released history is a corrected historical panel; the
corrections are declared for a future chain point (`VINTAGES.md` states the policy).
Use the frozen folder to replicate published work; use the refresh when you need
2024; read the errata file before building new work on the affected series.

## Files

Each vintage folder holds the same scores on five occupational classifications, in
three formats:

- `daioe_onetsoc2010.*` — O*NET-SOC 2010, the level the index is constructed at
- `daioe_soc2010.*` — US SOC 2010
- `daioe_isco08.*` — ISCO-08
- `daioe_ssyk96.*`, `daioe_ssyk2012.*` — Swedish SSYK
- `.dta` (Stata), `.xlsx` (Excel), and `.tsv` (tab-separated text; read with
  `pd.read_csv(f, sep="\\t")` in Python or `import delimited, delimiters(tab)` in
  Stata).

Each panel's unique key is (occupation code, `year`). Empty cells are missing
values, not zeros. `DATA_DICTIONARY.json` and `DATA_DICTIONARY.md` in the bundle
root give the exact schema of every table — columns, dtypes, row counts, year
ranges and asserted keys — generated from the staged files at build time.

## Columns

| column | meaning |
|---|---|
| occupation code, `year` | the unit of observation |
| `daioe_allapps` | the aggregate index over the nine original applications: cumulative exposure to AI progress |
| `daioe_<subdomain>` | the same for one capability subdomain: `stratgames` (abstract strategy games), `videogames` (real-time video games), `imgrec` (image recognition), `imgcompr` (image comprehension / visual question answering), `imggen` (image generation), `readcompr` (reading comprehension), `lngmod` (language modelling), `translat` (translation), `speechrec` (speech recognition) |
| `daioe_genai` | generative-AI composite (membership documented per vintage in `VINTAGES.md`) |
| `pctl_rank_*` | within-year percentile rank of the corresponding index, legacy tie convention — read the tie warning below before using |
| `pctl_mid_*` | (from v1.1.0) tie-invariant within-year midrank percentile: identical values share identical percentiles; prefer these where ties could matter |

## Percentile ranks and ties

The percentile ranks are the original published columns and carry a legacy tie
convention: inside a group of occupations whose substantive value is identical in a
year, the ranks differ only by historical row order. In an all-tie year (reading
comprehension 2013 is one: every occupation's cumulative is the same) the rank
spread is entirely arbitrary. Use the ranks for coarse within-year standing; where
ties could matter, or for anything quantitative, use the substantive `daioe_*`
columns, which never depend on tie order — or, from v1.1.0, the tie-invariant
`pctl_mid_*` companions. `VINTAGES.md` documents the convention and its
consequences for regeneration from code.

## Reading the scores

The index is cumulative and has no natural units, so what to compare depends on the
question. For cross-sectional standing within a year, the percentile ranks give an
ordinal reading, subject to the tie warning above. For levels and growth over time,
rescale the raw values to the frozen-window peak as documented in
`DOCUMENTATION.md` section 5 of the repository; raw cross-year comparisons are
meaningful but combine common capability progress with occupational ability
weights, so interpret them against the estimand you actually want.

## A property worth knowing before you use it

Benchmarks enter and retire as research moves, so an application's basket thins once
its benchmarks are solved, and the subdomain series are strongly correlated with one
another. Specifications that estimate several subdomain effects jointly may
therefore be unstable or hard to interpret, and their measurement coverage changes
over time. Both properties are documented rather than left to be discovered; see
`DOCUMENTATION.md` in the repository.

## Provenance

`provenance/` lists every measurement recorded from Papers with Code, with the
source paper associated with each archived record. `human_anchors_v1.csv` holds
every declared reference value with its source, quoted evidence and anchor kind.
`LICENSE-DATA` records the upstream sources and their licences.

## Licence and citation

The project-authored scores, documentation and metadata in this bundle are
CC BY 4.0: use freely, including commercially, with credit. Upstream source
measurements remain subject to their own terms, recorded in `LICENSE-DATA`. Cite
the Zenodo record and the accompanying paper; `CITATION.cff` in the repository has
the citation form for this version.

## Integrity

`SHA256SUMS` covers every payload file except itself. Verify from the bundle root
with `shasum -a 256 -c SHA256SUMS`.
"""


if __name__ == "__main__":
    main()
