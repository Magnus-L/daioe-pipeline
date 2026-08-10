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
     ROOT / "data" / "out_refresh2024_snapshot" / "Publication",
     "The 2024 annual refresh of surviving series."),
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
    (ROOT / "data" / "derived" / "pwc_provenance.csv", "provenance/pwc_provenance.csv"),
    (ROOT / "data" / "derived" / "pwc_provenance_README.md", "provenance/README.md"),
]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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
                shutil.copy2(f, dst / f.name)
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

Code, documentation and the full construction pipeline:
https://github.com/Magnus-L/daioe-pipeline

## The folders are different objects

| folder | what it is |
|---|---|
{rows}

**They are not interchangeable.** The frozen index underlies the published estimates;
the 2024 refresh extends the series and will not reproduce published numbers. Cite the
vintage you used.

The 2025-onward vintage is not in this release. It exists, but three of its properties
are still provisional, so it ships separately as v1.1.0 rather than being frozen into a
permanent record before it settles.

## Files

Each vintage folder holds the same scores on five occupational classifications, in
three formats:

- `daioe_onetsoc2010.*` — O*NET-SOC 2010, the level the index is constructed at
- `daioe_soc2010.*` — US SOC 2010
- `daioe_isco08.*` — ISCO-08
- `daioe_ssyk96.*`, `daioe_ssyk2012.*` — Swedish SSYK
- `.csv` (tab-separated), `.dta` (Stata), `.xlsx` (Excel)

## Columns

| column | meaning |
|---|---|
| occupation code, `year` | the unit of observation |
| `daioe_allapps` | the aggregate index: cumulative exposure to AI progress |
| `daioe_<subdomain>` | the same for one of nine capability subdomains |
| `daioe_genai` | generative-AI composite |
| `pctl_rank_*` | within-year percentile rank of the corresponding index |

The index is cumulative, so levels rise mechanically over time; comparisons should be
made within a year, across occupations, which is what the percentile ranks give you
directly.

## A property worth knowing before you use it

Benchmarks enter and retire as research moves, so an application's basket thins once its
benchmarks are solved, and the subdomain series are strongly correlated with one
another. Attributing an effect to a single capability is therefore weakly identified.
Both properties are documented rather than left to be discovered; see `DOCUMENTATION.md`
in the repository.

## Provenance

`provenance/` lists every measurement recorded from Papers with Code, with the paper
that first published it. `LICENSE-DATA` records the upstream sources and their licences.

## Licence and citation

CC BY 4.0: use freely, including commercially, with credit. Cite the Zenodo record and
the accompanying paper; `CITATION.cff` in the repository has the current form.

## Integrity

`SHA256SUMS` covers every file. Verify with `shasum -a 256 -c SHA256SUMS`.
"""


if __name__ == "__main__":
    main()
