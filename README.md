# DAIOE: how exposed is each occupation to AI?

DAIOE scores every occupation by how applicable AI's measured capabilities are to
what the occupation does, every year since 2012. It is built from progress on public
AI benchmarks, so exposure moves as capabilities arrive. A high score means AI can be
applied to much of the work; it is not a forecast of job loss.

## Just the scores

One CSV per classification, ready to open in Excel, Stata, R or Python:

| Classification | Latest year (2025), one row per occupation | All years, 2012–2025 |
|---|---|---|
| ISCO-08 (international) | [`scores/daioe_isco08_2025.csv`](scores/daioe_isco08_2025.csv) | [`scores/daioe_isco08_all_years.csv`](scores/daioe_isco08_all_years.csv) |
| SOC 2010 (United States) | [`scores/daioe_soc2010_2025.csv`](scores/daioe_soc2010_2025.csv) | [`scores/daioe_soc2010_all_years.csv`](scores/daioe_soc2010_all_years.csv) |
| SSYK 2012 (Sweden, Swedish titles) | [`scores/daioe_ssyk2012_2025.csv`](scores/daioe_ssyk2012_2025.csv) | [`scores/daioe_ssyk2012_all_years.csv`](scores/daioe_ssyk2012_all_years.csv) |

Each file has seven columns:

| Column | Meaning |
|---|---|
| `code`, `title` | the occupation (4-digit ISCO-08 or SSYK 2012; 6-digit SOC 2010) |
| `year` | the year the score refers to |
| `genai` | exposure to **generative AI** (language models, image generation, conversation, software engineering) |
| `genai_pctl` | its percentile among all occupations that year: 90 means more exposed than 90 per cent of occupations |
| `allai` | exposure to **all AI** (all thirteen capability areas) |
| `allai_pctl` | its percentile, as above |

Read the percentiles first. The scores themselves have no natural unit: they rank
occupations and show change over time, but a value of 10 does not mean "10 per cent".

In Python, one line: `pd.read_csv("https://raw.githubusercontent.com/Magnus-L/daioe-pipeline/main/scores/daioe_isco08_2025.csv", dtype={"code": str})`

Prefer to browse? Search any occupation, in English or Swedish, on the
[DAIOE page](https://ai-econlab.com/daioe/).

These files are taken from the citable release (v1.1.0, 2025 vintage,
https://doi.org/10.5281/zenodo.22551410) by `scripts/build_simple_scores.py`, which
checks the release's checksums first. Cite that DOI (see "Citing" below).

## Going further: the full release

The release on Zenodo adds the thirteen capability areas one by one, the legacy
composites the paper uses, two more classifications (O\*NET-SOC, SSYK 96) and Stata
and Excel versions. A few lines get you the full ranking and one occupation's path
over time. In Python, from the unzipped bundle:

```python
import pandas as pd
d = pd.read_stata("vintage-2025/daioe_ssyk2012.dta")          # or any taxonomy panel
titles = pd.read_csv("occupation_titles_ssyk.csv", dtype={"code": str}).query("taxonomy=='ssyk2012'")
ranked = (d[d.year == 2025].dropna(subset=["daioe_g2gen"])     # some codes carry no score
          .assign(code=lambda x: x.ssyk2012_4.astype(int).astype(str).str.zfill(4))
          .merge(titles, on="code")
          .sort_values("daioe_g2gen", ascending=False)
          )[["code", "title", "daioe_g2gen", "pctl_mid_g2gen"]]   # most to least exposed
top10, bottom10 = ranked.head(10), ranked.tail(10)
path = d[d.ssyk2012_4.astype(int) == 2512][["year", "daioe_g2gen"]]   # one occupation over time
```

Or in Stata:

```stata
use vintage-2025/daioe_ssyk2012, clear
keep if year == 2025 & !missing(daioe_g2gen)
gen code = string(ssyk2012_4, "%04.0f")
preserve
import delimited occupation_titles_ssyk.csv, clear stringcols(2)
keep if taxonomy == "ssyk2012"
tempfile t
save `t'
restore
merge 1:1 code using `t', keep(match) nogen
gsort -daioe_g2gen                                        // most to least exposed
list code title daioe_g2gen pctl_mid_g2gen in 1/10        // top 10
list code title daioe_g2gen pctl_mid_g2gen in -10/l       // bottom 10
```

`pctl_mid_*` is the tie-safe percentile (midrank within year). To standardise the way
the paper does, merge `standardisation_moments_v1.csv` and compute
`z = (value - mean) / sd`. Everything else (vintages, caveats, rescaling) is in the
two documents this README points to.

## What the release contains

| | |
|---|---|
| Coverage | Every occupation in each released taxonomy panel, annually, 2010–2023 in the frozen index (per year: 966 O\*NET-SOC, 772 SOC 2010, 438 ISCO-08, 429 SSYK 2012, 354 SSYK 96 occupations) |
| Decomposition | An aggregate index, nine capability subdomains, and a generative-AI composite (v1.1.0 adds two subdomains, two second-generation composites and a balanced companion) |
| Classifications | O\*NET-SOC, SOC 2010, ISCO-08, SSYK 96, SSYK 2012; plus a SOC 2018 panel export on the frozen window, labelled as such and not in the publication format |
| Formats | Stata `.dta` (the verified originals), with TSV and Excel derivatives; the standardisation moments the paper uses ship as a small CSV |
| Built from | Public AI benchmark results and O\*NET occupational ability profiles |

Scores are distributed via Zenodo. This repository holds the code that builds them, its
test suite, and the documentation.

## Which vintage to use, and why it matters

**The vintages are separate objects and are not interchangeable.** Mixing them
silently changes published numbers, so the release keeps them apart and asks you to
cite the one you used.

- **Frozen 2010–2023**: the index behind the published estimates. Use it to replicate,
  or to compare against published work.
- **2024 refresh**: appends 2024 under the seam discipline. Superseded for current
  analysis by the 2025 vintage; kept so that work done on it can be reproduced.
- **2025 vintage (v1.1.0)**: the newest released object. It adds two application
  areas, two second-generation composites (overall and generative) and a balanced
  nine-member companion, while the legacy composites keep their original
  membership. Use it for current analysis.

`VINTAGES.md` is the full record of what each vintage contains and what the freeze
guarantee covers.

## Citing

Cite the release *and* the paper, and name the object you used. Both matter: the
release fixes which version of the measure, the paper documents what it is.

- **This version (v1.1.1):** https://doi.org/10.5281/zenodo.24494713 (no score changes from v1.1.0; adds SOC 2018 in the common format)
- **v1.1.0:** https://doi.org/10.5281/zenodo.22551410
- **v1.0.0 (the frozen 2010–2023 index the paper estimates on):** https://doi.org/10.5281/zenodo.21873968
- **All versions:** https://doi.org/10.5281/zenodo.21873967
- A release contains several objects, so cite the DOI, the object ("frozen 2010–2023
  index", "2024 refresh" or "2025 vintage"), and the filename you loaded.
- **The paper:** Engberg et al., "AI Unboxed: AI Exposure and Clerical Employment
  within Firms". The full bibliographic form is in `CITATION.cff`, updated on publication.

`CITATION.cff` carries the machine-readable form; GitHub's "Cite this repository"
button reads it.

## Licence

Code is MIT (`LICENSE`). The scores are CC BY 4.0 (`LICENSE-DATA`): use them for
anything, including commercially, with credit. `LICENSE-DATA` also records where
every benchmark measurement came from and the licences those sources carry.

## Before you rely on it

Read `DOCUMENTATION.md`, the public technical reference, in particular the sections
“How new series and subdomains enter” and “The five composites, and which to use”. Where the paper's appendix and
the implementation differ, the implementation is authoritative; the differences are
the documented residual classes in `VALIDATION.md`.

Two properties are worth knowing up front. Benchmarks enter and retire over time, so
an application's basket thins as its benchmarks are solved. Moreover, the subdomain
series are highly correlated with one another, which limits how far the decomposition
can attribute an effect to any single capability.

## Rebuilding or extending the measure

`BUILDING.md` is the developer reference: environment, the five build stages, the
validation bar, and how annual updates, new taxonomies, new benchmark series and
vintage assembly work. The build's substantive index values are deterministic and
validated against the frozen original outputs; file hashes and tie-order details are
not, and `BUILDING.md` explains the distinction. A full build takes about 75 seconds.
