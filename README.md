# DAIOE — Dynamic AI Occupational Exposure

**How exposed is an occupation to artificial intelligence, and when did that exposure
arrive?** DAIOE answers both. It converts measured performance gains on public AI
benchmarks into exposure scores for every occupation *in every year*, so exposure moves
as capabilities actually arrive rather than sitting as a single static score.

That time dimension is the point. A static index can tell you which occupations look
exposed; a dynamic one lets you ask whether labour-market outcomes moved *when* the
relevant capabilities did, which is a testable claim rather than a correlation.

## What you get

| | |
|---|---|
| Coverage | Every occupation, annually, 2010–2023 in the frozen index |
| Breakdown | An aggregate index plus nine capability subdomains and a generative-AI composite |
| Classifications | O\*NET-SOC, SOC 2010, ISCO-08, SSYK 96, SSYK 2012; a SOC 2018 build ships alongside |
| Formats | CSV, Stata `.dta`, Excel |
| Built from | Public AI benchmark results and O\*NET occupational ability profiles |

Scores are published on Zenodo; this repository holds the code that builds them, its
test suite, and the documentation.

## Which vintage to use, and why it matters

**The vintages are separate objects and are not interchangeable.** Mixing them silently
changes published numbers, so the release keeps them apart and asks you to cite the one
you used.

- **Frozen 2010–2023** — the index behind the published estimates. Use this to replicate
  or to compare against published work.
- **2024 refresh**, **SOC 2018 build**, **2025-onward vintage** — later objects. Use
  these for current analysis, not for replication.

## Citing

Cite the release (see `CITATION.cff`) *and* the paper. Both matter: the release fixes
which version of the measure you used, the paper documents what it is.

## Licence

Code is MIT (`LICENSE`). The scores are CC BY 4.0 (`LICENSE-DATA`) — use them for
anything, including commercially, with credit. `LICENSE-DATA` also records where every
benchmark measurement came from and the licences those sources carry.

## Before you rely on it

Read `DOCUMENTATION.md`, and in particular the sections on how series are admitted and
on basket composition. Two properties are worth knowing up front: benchmarks enter and
retire over time, so an application's basket thins as its benchmarks are solved, and the
subdomain series are highly correlated with one another, which limits how far the
decomposition can attribute an effect to any single capability. Both are documented
rather than left for you to discover.

---

*The rest of this file is for people rebuilding or extending the measure.*

## What this repository is

A faithful Python port of Erik Engberg's Stata construction of DAIOE, validated
byte-near-exactly against the frozen Stata outputs, with a config-driven path to annual
updates and additional occupational classifications. It serves both the *AI Unboxed*
paper and the DAIOE-extensions paper.

## Why
The only time-varying input to DAIOE is the AI benchmark-progress vector (Δp_it). The
O*NET relevance matrix r_oj, the Felten mapping matrix x_ij, the social-skill discount
and δ=2 are fixed. So the engine is deterministic matrix algebra, and Erik's existing
output `.dta` files are an exact ground truth. Benchmark collection is manual (EFF +
Papers With Code; no Hugging Face), so an annual refresh = append benchmark rows + bump
`year_final`.

## Layout
```
config.yaml            run parameters (mirrors 0_2_settings.do)
run_all.py             entry point: stages 1-5 + validation report
src/daioe/
  config.py io.py stata_ops.py validate.py
  stage1_onet.py  stage2_ai_progress.py  stage3_mapping.py
  stage4_index.py stage5_taxonomies.py
tests/                 unit tests for the Stata-idiom shims
data/  raw,enriched_ref,reference -> read-only symlinks into the Stata source
       out/            our outputs
reports/               validation_<ts>.md
```

## The five stages (run order; each validated against a Stata `.dta`)
1. **stage1_onet** — r_oj (`element_impact`) + S_o (social skills) from O*NET 22.2.
2. **stage2_ai_progress** — Δp_it from benchmark SOTA frontiers (the time-varying input).
3. **stage3_mapping** — Felten x_ij mapping matrix.
4. **stage4_index** — Δe_jt → Δe_ot → social×square×10 → cumulate → percentile rank.
5. **stage5_taxonomies** — translate SOC2010 → ISCO08/SSYK2012/SSYK96 (+ SOC2018/SSYK2025),
   merge comparator indices, write internal + publication panels.

Stages 1–3 are independent; 4 needs 1–3; 5 needs 4.

## Environment
```bash
python3.10 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q          # expect 12 passed
```
Pinned and verified 4 Aug 2026 on Python 3.10.9. `numpy` and `pandas` are pinned hard
because the bit-exactness claim depends on float32 storage semantics and on groupby
summation order; re-run the full validation before changing either. Three dependencies
(`pyarrow`, `xlrd`, `openpyxl`) are loaded implicitly by pandas and appear in no import
statement — see the header of `requirements.txt`.

## Run
```bash
python scripts/preflight.py        # check every input resolves BEFORE running
python run_all.py                  # all stages + validation report
python run_all.py --no-validate    # build only (see the note below)
python run_all.py --stages 1,2,3   # subset
pytest -q                          # shim unit tests
```
A full build takes about 75 seconds.

**Validation currently cannot run on a fresh checkout.** `data/reference` and
`data/enriched_ref` point into `~/Downloads/DAIOE 20260527/`, which no longer exists;
the July restore brought back `1_data_ore` only, so `data/raw` resolves and the other
two do not. Every stage builds, and `--no-validate` completes, but `compare_to_dta`
dies on the first missing target. Restoring `2_data_enriched` and `3_data_jewelry` from
the same Drive share, into `data_source/DAIOE_20260527/Data/`, and repointing the two
symlinks is what makes `run_all.py` green again.

## Annual update (Phase 2)
Append the new year's benchmark rows to `measures_metrics_newdata2023.xlsx`, bump
`year_final` in `config.yaml`, rerun. The 2010–2023 slice must still match the frozen
targets; ≥2024 is checked for internal consistency.

## Add a taxonomy (Phase 3)
Add an entry to `taxonomies` in `config.yaml` (crosswalk path, key, level rule) and drop
the crosswalk into the data folder. SSYK2025 is blocked on an SCB crosswalk.

**SOC2018**: this README and both configs previously said the crosswalk was present in
the repo. It was not. It is now derived and audited — `scripts/build_soc2018_crosswalk_20260804.py`
writes `data/derived/soc2010_to_soc2018.dta` (913 pairs) and
`notes/soc2018-inventory-2026-08-04.md` records the round-trip verification and the two
open decisions. It is deliberately **not** wired into `config.yaml`: the commented entry
names a `.csv` where `_build_crosswalk_taxonomy` calls `read_dta`, and crosswalks resolve
under `data/raw/`, which is a symlink into the delivered source tree.

## Validation bar
A column passes if max|got−ref| ≤ 1e-6 (internal/double) and matches float32 publication
storage (1e-5); any worse column is flagged in the report rather than silently passed.
**The Stata code is authoritative over the paper appendix** wherever they differ.

## Refresh with benchmark updates (Phase 2, Track A)
The 2024 refresh procedure (established 2026-07-07; see `notes/track-a-*.md`):
1. Build/refresh the update workbook: `python scripts/build_crosswalk.py` (flattens
   the PwC archive dump; cached) then `python scripts/build_update_workbook.py`
   (extracts post-cutoff rows for the verified crosswalk into
   `data/updates/measures_updates_2024plus.xlsx`).
2. Point a config at it: `benchmark_updates: [data/updates/...xlsx]`, bump
   `year_final` (see `config-refresh2024.yaml`).
3. Run `python run_all.py --config config-refresh2024.yaml --stages 2,4,5
   --no-validate` — full-deviation vs the frozen targets is EXPECTED in refresh
   mode (the update revises history); use `python scripts/refresh_report.py` for
   the seam quantification instead.
4. Release gate: no 2024+ value circulates without `notes/track-a-coverage-audit.md`
   attached; seam policy per `notes/checkpoint2-seam-policy.md`.

## Documentation
`DOCUMENTATION.md` is the PUBLIC technical reference (measure, vintage policy, admission
rules, current vintage, changelog) — public-safe by construction, updated per vintage,
publishable to the ai-econlab.com DAIOE page. `notes/ISSUES-and-ideas.md` is the PRIVATE
counterpart: curated open issues and improvement ideas, feeding the co-author meetings.

## Licence and citation
Two licences, because this repository ships two different things.

- **Code** (`src/`, `scripts/`, `tests/`, `run_all.py`): MIT, see `LICENSE`.
- **Data** (the DAIOE occupation-year scores and derived files): CC BY 4.0, see
  `LICENSE-DATA`, which also lists the upstream licences the scores inherit from.

Cite via `CITATION.cff`. **Cite the vintage, not the repository**: the frozen 2010-2023
index behind the published estimates, the 2024 refresh, the SOC2018 build and the
2025-onward vintage are separate objects and mixing them silently changes published
numbers.

Provenance of the frozen source was measured on 10 August 2026: 190 of its 2,108
measurements were recorded from Papers with Code (CC BY-SA 4.0), concentrated in
2018-2023 where they are about half of all rows; EFF supplies the rest and declares its
measurements uncopyrightable. Every one of those 190 is now attributed to the paper that
published the measurement (`data/derived/pwc_provenance.csv`), so the release carries
published facts with their citations rather than an extract of that database, and ships
CC BY 4.0 throughout. Reasoning and evidence: `LICENSE-DATA`.

## Extensions: new series through the second door (Track B)
New metrics and subdomains enter via `benchmark_extensions` workbooks (two sheets,
seven guards in `stage2_ai_progress._load_extensions`; see
`notes/EXTENSION-door_2026-08-07.md`). Extension workbooks built so far:
- `data/updates/extension_gpqa_2026-08-07.xlsx` — GPQA Diamond (Epoch, CC BY 4.0),
  new metric under Language comprehension and QA, chained 2024.
- `data/updates/extension_tombench_2026-08-08.xlsx` — Theory of Mind on ToMBench
  (MIT; scores arXiv:2602.10625), FIRST series for the conversation application,
  chained 2024; built by `scripts/build_tombench_extension_20260808.py`, which also
  runs the freeze-history check (must print 0.00e+00). Design and caveats in
  `notes/EXTENSION-conversation-tombench_2026-08-08.md`.
- `data/updates/extension_swebench_2026-08-08.xlsx` — Software issue resolution on
  SWE-bench Verified (Epoch-run harness, CC BY 4.0; the leaderboard's CC BY-NC does
  not apply), FIRST series for application id 4 and the measure's first system_level
  protocol; ceiling anchor 95.0 PROVISIONAL pending the anchor convention. Built by
  `scripts/build_swebench_extension_20260808.py`; note
  `notes/EXTENSION-software-swebench_2026-08-08.md`.
None is wired into a committed config; the vintage assembly builds its config in
memory.

## The 2025 vintage (Track B B5)
`python scripts/assemble_vintage_2025_20260808.py` assembles the release under the
settled seam policy (frozen 2010-2023 immutable, 2024-2025 chained at 2023) with
three fatal gates: G1 splice integrity (0 frozen preliminary cells changed), G2
publication seam (every taxonomy panel bit-identical to the frozen pipeline's own
publication output over 2010-2023), G3 entry discipline (new-domain columns silent
before 2024). Every Erik decision is a flag: `--gpqa-parent qa`, `--allapps-rule
mean`, `--membership plus-new`; matrix/discount variants come from
`mapping/code/build_2024_variants.py` and land with the matrix decision. Output:
`data/vintage/<tag>/` + `reports/<tag>/RELEASE.md` (input sha256 manifest included).
