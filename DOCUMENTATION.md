# DAIOE — Technical Documentation

**Dynamic AI Occupational Exposure (DAIOE)** translates performance improvements across
public AI benchmarks into occupation-year exposure scores, separately for AI subdomains
and composites. This document is the public technical reference for the measure and its
vintages. It is updated with each vintage release; the construction of record is the one
in the paper and its online appendix, which this document summarises but never overrides.

*Maintained by the AI-Econ Lab (Örebro University / RATIO). Contact: see ai-econlab.com.*

---

## 1. The measure in brief

DAIOE combines three ingredients: annual AI progress per application (state-of-the-art
frontiers over public benchmarks, rescaled per Felten et al. 2018 so linear increases
reflect exponential improvement); an application-to-ability relevance matrix; and O*NET
occupation ability profiles with a social-skill discount. Progress raises the exposure of
the abilities an application is relevant for, occupations inherit exposure through their
ability profiles, and the cumulative sum over years is the index level. Sub-indices are
built per application, plus composites (all applications; generative AI).

Panels are published for five occupational taxonomies — O*NET-SOC 2010, SOC 2010,
ISCO-08, SSYK 2012 and SSYK 96, each with per-year percentile ranks — plus a SOC 2018
panel export (not in publication format).

## 2. Vintages

- **The frozen window, 2010–2023,** is the series estimated in the paper. It is immutable:
  no later data, source revision or membership change ever alters a published 2010–2023
  value; the assembly gates enforce bit-identity of every published cell across vintages.
  The released panels are unstandardised. Standardisation to frozen 2010–2020 moments
  happens at estimation, where the moments are computed once and reused, so appending a
  vintage never rescales an estimated year. Users who standardise a later vintage
  themselves must compute moments on 2010–2020 only, never on the full window.
  <!-- Restated 2026-08-08 (code review): the earlier wording implied the shipped panels
  were standardised with a mean-zero/sd-one 2010–2020 test; they are raw, and the enforced
  invariant is cell bit-identity (gates G1/G2/G2b). -->
- **Vintages are labelled by coverage window** (e.g. *DAIOE v2025* covers 2010–2025) and
  are separate, citable objects. Values beyond 2023 are revisable in later vintages, as
  evaluation harnesses score earlier models retrospectively; the frozen window is not.
- **Chain points.** All basket, series and membership changes take effect at a vintage's
  chain point (v2025: the 2023–2024 seam), never inside published history. This follows
  the convention of chain-linked official statistics: entry into the basket lags
  capability by construction, the bias direction is known and disclosed, and history is
  never backfilled — backfilling with hindsight-selected benchmarks would overstate
  progress precisely where AI later succeeded.

## 3. How new series and subdomains enter

A series is admitted only with a complete declaration: scale (one of eight declared
families), a numeric human anchor with source and verbatim supporting quote, an evaluation
protocol (`pure_model` or `system_level`, never mixed within a series), a chain year at or
after the current vintage's chain point, a redistribution-clean licence, and provenance
(source, retrieval date, file hashes). Admission is composition-neutral: an entrant
contributes nothing in its entry year. Automated gates verify on every assembly that the
published window is bit-identical (all taxonomies, single precision) and that no admitted
series carries a value before its chain point.

## 4. Vintage v2025 (assembled August 2026)

**Sources for the appended years:** the recovered Papers with Code archive (2024 refresh of
surviving series) and Epoch AI's benchmark data (CC BY 4.0) for harness-run and collected
series.

**Series admitted at the 2024 chain point** (the full declarations, anchors and quoted
evidence are in `VINTAGES.md` and `data/derived/human_anchors_v1.csv`):

| Subdomain | Series | Protocol | Human anchor | Licence / permission |
|---|---|---|---|---|
| Agentic task execution | METR task horizons, 80% reliability (primary) | system_level | 960 min, instrument ceiling | METR data with written permission (cite METR; not affiliated) |
| Agentic task execution | OSWorld | system_level | 72.36 (human) | CC BY 4.0 (Epoch collection) |
| Agentic task execution | GDPval | system_level | 50 (parity by construction: win rate vs human professionals) | CC BY 4.0 (Epoch collection) |
| Mathematical & scientific reasoning | GPQA Diamond (Epoch-run harness) | pure_model | 81.3 (expert accuracy) | CC BY 4.0 |
| Mathematical & scientific reasoning | MATH Level 5 | pure_model | 90 (expert; full-set figure, declared caveat) | CC BY 4.0 (Epoch collection) |
| Software engineering | SWE-bench Verified (Epoch-run harness) | system_level | 95.0 ceiling (discounted by convention) | CC BY 4.0 |
| Conversation | Theory of Mind on ToMBench | pure_model | 86.1 (organiser human baseline) | MIT; scores arXiv:2602.10625 |
| Language comprehension & QA | SimpleBench | pure_model | 83.7 (organisers' human baseline, n=9, declared caveat) | organiser-published |

TheAgentCompany is carried as a corroboration series outside the basket (95.0 ceiling by
the SWE-bench convention; pinned to one simulation environment so an environment change is
never booked as capability). The METR 50%-reliability variant was retired when frontier
systems outgrew its 960-minute range; the two reliability bars are one construct and are
never in the basket together.

**Two new application areas with exposure columns.** Agentic task execution and
mathematical and scientific reasoning enter with their own occupation exposure columns
(`daioe_agentic`, `daioe_mathsci`), built from the Felten-Raj-Seamans 2018 expert matrix's
two technical-problem rows, used unedited and validated by two independent LLM re-scorings
from different vendors (details in `VINTAGES.md`). Both columns are chained: no values
before 2024.

**Membership change:** the generative-AI composite keeps its name and broadens at the
chain point from {image generation, language modelling} to also include conversation and
software engineering; the narrow-membership continuation is recorded alongside. The frozen
generative-AI column is unaffected. The two new application areas are not members of
either original composite. A second-generation overall composite (`daioe_g2all`) is
published as an additional column with a complete 2010–2025 history of its own; its
standardisation table ships as `data/derived/g2_sigma_v1.csv` and its construction and
checks are documented in `VINTAGES.md`.

**Known caveats, stated rather than discovered:** (i) a newly admitted series' first
measured year is computed against its entry-year frontier, and where that baseline is thin,
late-entry-year capability is booked to the first measured year — SWE-bench Verified (one
2024 evaluation) and ToMBench (two) are the thin cases, so their 2025 increments are upper
bounds pending fuller harness coverage; (ii) five of nine original applications have no
living 2025 source (repository sunset, not capability plateau), so composite values ship
with a coverage audit; (iii) anchor kinds are declared per series — human, expert,
instrument ceiling, ceiling by convention (discounted), and parity by construction — and
recorded with quoted evidence in the anchors file.

## 5. The four aggregates, and which to use

From the 2025 vintage the release carries three composite indices beside the
subdomains, and they answer different questions.

**`daioe_genai` — exposure to the generative wave.** A thematic composite: how
exposed an occupation is to AI systems that produce content — text (language
modelling), images (image generation), dialogue (conversation) and code (software
engineering). Raw-sum construction; frozen history intact; the membership broadens
from the original two to these four at the 2023–24 seam, so a seam-crossing
movement mixes progress with membership. Use it when the question is specifically
about generative AI, which is usually what policy audiences mean by "AI".

**`daioe_agentic` — exposure to AI that does rather than produces.** A subdomain:
autonomous multi-step execution of real computer work, measured by how long a
human task the system completes reliably (METR task horizons, with OSWorld and
GDPval). Conceptually distinct from generative capability: a chatbot drafts an
email, an agent clears an inbox. Chained at 2024, so its history is short; it is
the domain that moved most in 2025.

**`daioe_mathsci` — exposure to hard structured reasoning.** A subdomain:
graduate-level scientific and mathematical problem-solving (GPQA Diamond, MATH
Level 5). A third capability axis — neither producing content nor executing
tasks. Chained at 2024.

**`daioe_g2all` — exposure to measured AI progress overall.** The
second-generation aggregate: each application's annual progress expressed in
units of its own historical variation and averaged over the applications observed
that year, which is what lets generative, agentic and reasoning domains sit in
one number without any of them dominating by scale. Values over the full window;
not a constant-basket series. Use it when the question is overall exposure, now
and in later vintages.

**The relations in one breath:** genai, agentic and mathsci are three kinds of AI
capability — producing, doing, reasoning — and g2all is the roof over all of
them. `daioe_allapps` remains the legacy overall index, aggregating the nine
original applications unchanged, and stays the replication object behind the
published estimates; for current monitoring from 2024 onwards, `daioe_g2all` is
the headline. The two agree closely where they overlap (within-year rank
agreement 0.97 by 2016, 0.99 in 2023 and 2025).

## 6. Reading and rescaling the scores

The released panels are raw index values. The index has no natural units: a level or a
change is meaningful only relative to other occupation-years, and every estimate in the
paper standardises before use. Two presentation conventions cover most needs.

**Cross-sectional standing: percentile ranks.** Shipped in every panel
(`pctl_rank_allapps`), the occupation's within-year percentile. Ordinal: read "more
exposed than X per cent of occupations that year". Distances and growth are not
preserved; the top occupation sits near 100 every year even as its raw exposure grows.

**Level and growth: rescale to the frozen-window peak.** For a cardinal reading, divide
by the panel's frozen-window maximum and multiply by 100:

```
score_rel_max = 100 * value / max(value)   # max over all occupation-years, 2010–2023,
                                           # in the taxonomy panel you use
```

The result reads "per cent of the most exposed occupation-year in the frozen window".
The transformation is linear, so ratios and time paths survive: an occupation at 31 in
2015 and 62 in 2023 doubled its exposure. Compute the denominator once, on the frozen
2010–2023 years of your panel (one number per taxonomy), and reuse it unchanged for
later vintages; values above 100 then read as exposure beyond the frozen-window peak.
Never take each vintage's own maximum, which would rescale history with every release
and make numbers incomparable across versions. The same convention applies per
sub-index, each with its own frozen-window maximum; do not compare rescaled values
across sub-indices, whose maxima differ.

We deliberately ship raw values rather than a rescaled column: the raw cells are the
citable, bit-identical stratum the release gates protect and published work builds on,
and one canonical scale avoids version ambiguity. The rescaling is a one-line
transformation under the user's control; the same guidance, with worked examples, is on
the measure's page at ai-econlab.com.

## 7. Changelog

- **§4 updated** (25 Aug 2026): the 24 Aug admission round folded in — METR-80 primary
  agentic with OSWorld and GDPval; MATH Level 5; SimpleBench; TheAgentCompany moved to
  corroboration outside the basket; the two activated exposure columns and the
  second-generation composite documented; anchor kinds ratified. The 2024 refresh was
  rebuilt under the seam discipline the same day (frozen window verbatim, 2024 chained).
- **§5 added** (11 Aug 2026): reading and rescaling guidance — the relative-to-peak
  transformation is documented for users rather than shipped as a column.
- **v2025** (Aug 2026): first vintage beyond the frozen window; new subdomain series
  admitted at the 2024 chain point; generative-AI membership broadened; gates and
  coverage audit introduced.
- **Frozen 2010–2023** (2023–2024): the paper's series; Stata construction ported to
  Python and validated bit-exact across all published panels.

What each released vintage contains, and why, is documented in [VINTAGES.md](VINTAGES.md).
