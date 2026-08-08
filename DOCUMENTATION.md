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

Panels are published for six occupational taxonomies: O*NET-SOC 2010, SOC 2010, SOC 2018,
ISCO-08, SSYK 2012 and SSYK 96, with per-year percentile ranks.

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

**Series admitted at the 2024 chain point:**

| Subdomain | Series | Protocol | Human anchor | Licence |
|---|---|---|---|---|
| Conversation | Theory of Mind on ToMBench | pure_model | 86.1 (organiser human baseline) | MIT; scores arXiv:2602.10625 |
| Software engineering | SWE-bench Verified (Epoch-run harness) | system_level | 95.0 ceiling, provisional | CC BY 4.0 |
| Mathematical & scientific reasoning | GPQA Diamond (Epoch-run harness) | pure_model | 81.3 (expert accuracy) | CC BY 4.0 |
| Agentic task execution | TheAgentCompany (interim, pending METR licensing) | system_level | ceiling, provisional | CC BY 4.0 (Epoch collection) |

**Membership change:** the generative-AI composite keeps its name and broadens at the
chain point from {image generation, language modelling} to also include conversation and
software engineering; the narrow-membership continuation is recorded alongside. The frozen
generative-AI column is unaffected.

**Known caveats, stated rather than discovered:** (i) a newly admitted series' first
measured year is computed against its entry-year frontier, and where that baseline is thin,
late-entry-year capability is booked to the first measured year — SWE-bench Verified
(single 2024 evaluation) is the thin case and its 2025 increment is an upper bound pending
fuller harness coverage; (ii) five of nine original applications have no living 2025
source (repository sunset, not capability plateau), so composite values ship with a
coverage audit; (iii) ceiling-type anchors (tasks human-resolved by construction) are
provisional pending a uniform anchor convention.

## 5. Changelog

- **v2025** (Aug 2026): first vintage beyond the frozen window; four subdomain series
  admitted; generative-AI membership broadened; gates and coverage audit introduced.
- **Frozen 2010–2023** (2023–2024): the paper's series; Stata construction ported to
  Python and validated bit-exact across all published panels.
