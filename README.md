# DAIOE — Dynamic AI Occupational Exposure

**How exposed is an occupation to artificial intelligence, and when did that exposure
arrive?** DAIOE answers both. It converts measured performance gains on public AI
benchmarks into exposure scores by occupation *and year*, so exposure moves as
capabilities actually arrive rather than sitting as a single static score.

That time dimension is the point. A static index can tell you which occupations look
exposed; a dynamic one lets you ask whether labour-market outcomes moved *when* the
relevant capabilities did, which is a testable claim rather than a correlation.

## What you get

| | |
|---|---|
| Coverage | Every occupation in each released taxonomy panel, annually, 2010–2023 in the frozen index (per year: 966 O\*NET-SOC, 772 SOC 2010, 438 ISCO-08, 429 SSYK 2012, 354 SSYK 96 occupations) |
| Breakdown | An aggregate index plus nine capability subdomains and a generative-AI composite |
| Classifications | O\*NET-SOC, SOC 2010, ISCO-08, SSYK 96, SSYK 2012; plus a SOC 2018 panel export on the frozen window (clearly labelled, not Publication format) |
| Formats | Stata `.dta` (the gated originals), with TSV and Excel derivatives |
| Built from | Public AI benchmark results and O\*NET occupational ability profiles |

Scores are published on Zenodo; this repository holds the code that builds them, its
test suite, and the documentation.

## Which vintage to use, and why it matters

**The vintages are separate objects and are not interchangeable.** Mixing them silently
changes published numbers, so the release keeps them apart and asks you to cite the one
you used.

- **Frozen 2010–2023** — the index behind the published estimates. Use this to replicate
  or to compare against published work.
- **2024 refresh** — the newest released object; appends 2024 under the seam discipline.
  Use it for current analysis.
- **2025 vintage (v1.1.0)** — forthcoming; adds two application areas and a
  second-generation composite. Use it for current analysis when released.

`VINTAGES.md` is the full record of what each vintage contains and what the freeze
guarantee covers.

## Citing

Cite the release *and* the paper, and name the object you used. Both matter: the
release fixes which version of the measure, the paper documents what it is.

- **This version (v1.0.0):** https://doi.org/10.5281/zenodo.21873968
- **Always the newest version:** the concept DOI on the Zenodo record
- Because v1.0.0 contains two objects, cite as: DOI, plus the object ("frozen
  2010-2023 index" or "2024 refresh"), plus the filename you loaded.
- The paper: Engberg et al., "AI Unboxed: Capability Arrival and the Clerical
  Decline" (full bibliographic form in `CITATION.cff`, updated on publication).
- The all-versions concept DOI appears at the top of the Zenodo record and is
  recorded here at first deposit.

`CITATION.cff` carries the machine-readable form; GitHub's "Cite this repository"
button reads it.

## Licence

Code is MIT (`LICENSE`). The scores are CC BY 4.0 (`LICENSE-DATA`) — use them for
anything, including commercially, with credit. `LICENSE-DATA` also records where every
benchmark measurement came from and the licences those sources carry.

## Before you rely on it

Read `DOCUMENTATION.md`, the public technical reference, and in particular the
sections on how series are admitted and on basket composition; `VINTAGES.md` is
the record of what each vintage contains. Where the paper's appendix and the
implementation differ, the implementation is authoritative and the differences
are the documented residual classes in `VALIDATION.md`. Two properties are worth knowing up front: benchmarks enter and
retire over time, so an application's basket thins as its benchmarks are solved, and the
subdomain series are highly correlated with one another, which limits how far the
decomposition can attribute an effect to any single capability. Both are documented
rather than left for you to discover.

## Rebuilding or extending the measure

`BUILDING.md` is the developer reference: environment, the five build stages, the
validation bar, and how annual updates, new taxonomies, new benchmark series and
vintage assembly work. The build's substantive index values are deterministic and
validated against the frozen original outputs (file hashes and tie-order details
are not; `BUILDING.md` explains the distinction), and a full build takes about
75 seconds.
