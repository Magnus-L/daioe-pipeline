# Building DAIOE

The developer reference: how the scores are built, validated, updated and released.
Users of the scores need `README.md`, `VINTAGES.md` and `DOCUMENTATION.md`; this file is for rebuilding or extending.

## What this repository is

A faithful Python port of the original Stata construction of DAIOE (Engberg), with a
config-driven path to annual updates and additional occupational classifications. The
only time-varying input is the AI benchmark-progress vector; the O\*NET relevance
matrix, the mapping matrix, the social-skill discount and its strength are fixed. The
engine is therefore deterministic matrix algebra, and the frozen Stata outputs serve as
the replication target the port is validated against.

## Layout

```
config.yaml            run parameters
run_all.py             entry point: stages 1-5 + validation report
src/daioe/             config, io, stata_ops, validate, stage1..stage5
tests/                 unit tests for the Stata-idiom shims
scripts/               update workbooks, extensions, vintage assembly, release bundle
data/                  raw and reference inputs (read-only), out/ for outputs
reports/               validation and release reports
```

## The five stages (run order; each validated against a frozen target)

1. **stage1_onet**: ability relevance r_oj and social intensity S_o from O\*NET 22.2.
2. **stage2_ai_progress**: benchmark progress from SOTA frontiers (the time-varying input).
3. **stage3_mapping**: the application-to-ability mapping matrix.
4. **stage4_index**: exposure increments, social discount, square, cumulate, ranks.
5. **stage5_taxonomies**: translate to the released classifications, merge comparator
   indices, write internal and publication panels.

Stages 1–3 are independent; 4 needs 1–3; 5 needs 4.

## Environment

```bash
python3.10 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q          # expect 61 passed (4 Sep 2026)
```

`numpy` and `pandas` are pinned hard because the reproduction claim depends on float32
storage semantics and on groupby summation order; re-run the full validation before
changing either. Three dependencies (`pyarrow`, `xlrd`, `openpyxl`) are loaded
implicitly by pandas; see the header of `requirements.txt`.

## Run

```bash
.venv/bin/python scripts/preflight.py   # check every input resolves BEFORE running
.venv/bin/python run_all.py             # all stages + validation report
.venv/bin/python run_all.py --stages 1,2,3
.venv/bin/python -m pytest -q
```

A full build takes about 75 seconds.

## Validation bar, and what "exact" means here

A column passes if max|got−ref| ≤ 1e-6 at internal double precision and matches
float32 publication storage at 1e-5; any worse column is flagged in the report, never
silently passed. The frozen files are a **replication target**: a clean build
reproduces every substantive `daioe_*` cell at stored precision, with two documented
residual classes (a set of half-rounding cells in one intermediate, and four source
errata retained by design; see `VALIDATION.md` and the errata section of
`VINTAGES.md`). Percentile ranks are order-dependent inside tie groups, so the legacy
`pctl_rank_*` columns are reproduced tie-aware-equivalently rather than
bit-identically; releases restore the deposited v1.0.0 rank values verbatim for the
frozen window, and from v1.1.0 every panel also carries tie-invariant `pctl_mid_*`
companions. Where the Stata code and the paper appendix differ, the Stata code is
authoritative.

Two build behaviours to know: re-running rewrites the `.dta` outputs' embedded
timestamps, so their file hashes change even when values reproduce (parquet and csv
are hash-stable); and release bundles source the frozen Publication folder from the
deposited originals, not from the pipeline's own export.

## Annual update

Append the new year's rows to the benchmark workbook, bump `year_final` in
`config.yaml`, rerun. The 2010–2023 slice must still match the frozen targets; later
years are checked for internal consistency. New series enter through the extension
door (below), never by editing frozen history.

There is also an internal **frontier-recomputation mode** (`benchmark_updates:` plus a
refresh config), used diagnostically to quantify what fuller archive coverage would
have implied. Its output deviates from the frozen targets by construction and is
never a release path: released refreshes are built under the seam discipline
(`VINTAGES.md`), which carries the frozen window verbatim and chains new years on the
frozen level.

## Add a taxonomy

Add an entry to `taxonomies` in `config.yaml` (crosswalk path, key, level rule) and
drop the crosswalk into the data folder. Current status: the five released
classifications are wired; a SOC 2018 crosswalk is derived and audited, and the v1.0.0 bundle ships its frozen-window panel export as an extra, clearly labelled as not Publication format; SSYK 2025 waits on an official SCB
crosswalk.

## Extensions: new benchmark series

New metrics and subdomains enter via `benchmark_extensions` workbooks (two sheets,
seven guards in `stage2_ai_progress._load_extensions`). Each extension workbook is
built by a dedicated script that also runs the freeze-history check (must print
0.00e+00). Extensions are never wired into a committed config; the vintage assembly
builds its configuration in memory from explicit flags.

## Vintage assembly

`scripts/assemble_vintage_2025_20260808.py` assembles a release under the seam policy
(frozen 2010–2023 immutable; later years chained at the seam) with three fatal gates:
G1 splice integrity (zero frozen cells changed), G2 publication seam (every taxonomy
panel cell-identical to the deposited frozen publication files over 2010–2023, on the
full v1.0.0 column set), G3 entry discipline (new-domain columns silent before their
chain year). Assembly decisions are explicit command-line flags recorded in the
release report; the shipped 2025 assembly (the v1.1.0 candidate) used
`--gpqa-parent maths`, `--allapps-rule survivors`, `--membership published`,
`--genai legacy`, `--agentic metr80`; the earlier `--genai broad` run was
superseded by the 4 September 2026 membership amendment (see `VINTAGES.md`).
The broadened generative composite is then built as a separate column by
`scripts/build_g2gen_composite_20260904.py` (standardised units over the four
generative applications, reusing `g2_sigma_v1.csv`), and
`scripts/wire_v110_release_rc2_20260904.py` wires the new columns
(`g2all`, `g2gen`, `agentic`, `mathsci`) into the release candidate's
publication panels. Output: `data/vintage/<tag>/` plus `reports/<tag>/RELEASE.md`
with an input sha256 manifest. Before any deposit,
`scripts/gate_panel_structure.py` additionally verifies every publication
panel's structure (no missing keys, unique occupation-year pairs, exact expected
row counts, and year-less rows only where the deposited v1.0.0 file carries the
same inherited rows).

## Release bundle

`scripts/build_release_bundle.py` stages the Zenodo upload (scores bundle + source
archive); `scripts/add_midrank_pctl_20260825.py` adds the tie-invariant midrank
companions and self-verifies. The bundle ships a per-table `DATA_DICTIONARY`, the
errata file with its guarded `apply_errata` mechanism (off in every build to date),
and the provenance sidecars and anchors file described in `VINTAGES.md`.
