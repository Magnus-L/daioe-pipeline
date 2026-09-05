# DAIOE — Dynamic AI Occupational Exposure

**How exposed is an occupation to artificial intelligence, to which capabilities, and
when did that exposure arrive?** DAIOE answers all three. It converts measured
performance gains on public AI benchmarks into exposure scores by occupation *and
year*, separately for nine capability subdomains and their composites. Exposure
therefore moves as capabilities arrive, instead of sitting as a single static score.

The two dimensions together are the unboxing in the paper's title. A static aggregate
can say which occupations look exposed. The subdomain scores describe what kind of AI
progress that exposure rests on, and the time dimension lets you ask whether
labour-market outcomes moved *when* the relevant capabilities did: a testable claim
rather than a correlation.

## Quick start

Three lines get you a ranked list; no manual needed. From the Zenodo bundle:

```python
import pandas as pd
d = pd.read_stata("refresh-2024/daioe_ssyk2012.dta")          # or any taxonomy panel
titles = pd.read_csv("occupation_titles_ssyk.csv", dtype={"code": str}).query("taxonomy=='ssyk2012'")
top10 = (d[d.year == 2024].nlargest(10, "daioe_allapps")
         .assign(code=lambda x: x.ssyk2012_4.astype(int).astype(str).str.zfill(4))
         .merge(titles, on="code"))[["code", "title", "daioe_allapps"]]
```

To standardise the way the paper does, merge `standardisation_moments_v1.csv`
and compute `z = (value - mean) / sd`. To cite, see "Citing" below. Everything
else (vintages, caveats, rescaling) is in the two documents this README
points to.

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
- **2024 refresh**: the newest released object; appends 2024 under the seam
  discipline. Use it for current analysis.
- **2025 vintage (v1.1.0)**: forthcoming. It adds two application areas, two
  second-generation composites (overall and generative) and a balanced
  nine-member companion, while the legacy composites keep their original
  membership. Use it for current analysis when released.

`VINTAGES.md` is the full record of what each vintage contains and what the freeze
guarantee covers.

## Citing

Cite the release *and* the paper, and name the object you used. Both matter: the
release fixes which version of the measure, the paper documents what it is.

- **This version (v1.0.0):** https://doi.org/10.5281/zenodo.21873968 (reserved;
  resolves once the first deposit is published)
- **All versions:** the concept DOI on the Zenodo record, added here at first deposit.
- v1.0.0 contains two objects, so cite the DOI, the object ("frozen 2010–2023 index"
  or "2024 refresh"), and the filename you loaded.
- **The paper:** Engberg et al., "AI Unboxed: Capability Arrival and the Clerical
  Decline". The full bibliographic form is in `CITATION.cff`, updated on publication.

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
