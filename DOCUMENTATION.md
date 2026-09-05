# DAIOE — Technical Documentation

**Dynamic AI Occupational Exposure (DAIOE)** translates performance improvements across
public AI benchmarks into occupation-year exposure scores, separately for AI subdomains
and composites. This document is the public technical reference for the measure and its
vintages, updated with each release.

**Authority.** For the frozen 2010–2023 construction, the paper and its online appendix
are the description of record; where the appendix and the implementation differ, the
implementation is authoritative and the differences are the documented residual classes
in `VALIDATION.md`. For everything after the frozen window, `VINTAGES.md` is the record.

*Maintained by the AI-Econ Lab (Örebro University / RATIO). Contact: see ai-econlab.com.*

---

## 1. The measure in brief

DAIOE combines three ingredients: annual AI progress per application (state-of-the-art
frontiers over public benchmarks, rescaled per Felten et al. 2018 so linear increases
reflect exponential improvement); an application-to-ability relevance matrix; and O*NET
occupation ability profiles with a social-skill discount. The construction order matters
and includes a nonlinear step: per occupation and year, the ability-weighted exposure
increment is discounted for social intensity, **squared**, scaled, and cumulated over
years to the index level. The squaring preserves the ordering of increments within a
year exactly (increments are non-negative) but not, in principle, the ordering of
cumulated levels; in the data the level rankings barely move (Spearman 0.97 or
higher against an unsquared variant in every year), and the paper reports the
headline estimate re-run on the unsquared index (Online Appendix, Section M).
One consequence is worth knowing: with squared increments the annual frequency is
substantive, since the same cumulative progress arriving in fewer, larger steps
yields a higher level. Composites aggregate at the
application level before this occupation-level chain.

The applications and their columns, with membership in each composite:

| Application | Column | Original? | In allapps | In genai | In g2gen | In g2all |
|---|---|---|---|---|---|---|
| Abstract strategy games | `daioe_stratgames` | yes | yes | – | – | yes |
| Real-time video games | `daioe_videogames` | yes | yes | – | – | yes |
| Image recognition | `daioe_imgrec` | yes | yes | – | – | yes |
| Image comprehension (incl. visual question answering) | `daioe_imgcompr` | yes | yes | – | – | yes |
| Image generation | `daioe_imggen` | yes | yes | yes | yes | yes |
| Reading comprehension (language comprehension and QA) | `daioe_readcompr` | yes | yes | – | – | yes |
| Language modelling | `daioe_lngmod` | yes | yes | yes | yes | yes |
| Translation | `daioe_translat` | yes | yes | – | – | yes |
| Speech recognition | `daioe_speechrec` | yes | yes | – | – | yes |
| Conversation¹ | *(no own column yet)* | 2024 entrant | – | – | yes | yes |
| Software engineering | *(no own column yet)* | 2024 entrant | – | – | yes | yes |
| Agentic task execution | `daioe_agentic` | 2024 entrant | – | – | – | yes |
| Mathematical and scientific reasoning | `daioe_mathsci` | 2024 entrant | – | – | – | yes |

¹ The released column set is the published paper's plus the two new application
areas; conversation and software engineering enter the composites as measured
members from 2024 and receive their own columns once their series thicken.

Panels are published for five occupational taxonomies (O*NET-SOC 2010, SOC 2010,
ISCO-08, SSYK 2012 and SSYK 96), each with per-year percentile companions. The v1.0.0
bundle additionally ships `soc2018/daioe_panel_soc2018.dta`, a SOC 2018 panel export on
the frozen window in the pipeline's internal panel schema (exposure changes and
cumulative levels; no percentile companions and no publication-format gating).

## 2. Vintages

- **The frozen window, 2010–2023,** is the series estimated in the paper. Its protection
  is precise: every 2010–2023 cell of the v1.0.0 column set (the `daioe_*` columns and
  their `pctl_rank_*` companions, plus SOC 2010's 68 inherited year-less rows) is
  verified cell-identical at stored precision on every assembly. Values after 2023 are
  revisable in later vintages; columns new to a vintage carry their own history and are
  outside this guarantee.
  The released panels are unstandardised. Standardisation to frozen 2010–2020 moments
  happens at estimation, where the moments are computed once and reused, so appending a
  vintage never rescales an estimated year; the window ends in 2020 so that the
  moments predate the estimation frontier and the 2021--2023 acceleration,
  keeping standardised coefficients in pre-shock units. Users who standardise a later vintage
  themselves must compute moments on 2010–2020 only, never on the full window.
- **Vintages are labelled by coverage window** (e.g. *DAIOE v2025* covers 2010–2025) and
  are separate, citable objects.
- **Year assignment.** A benchmark score is assigned to the year of the evaluated
  model's release, not the year of the evaluation, so an evaluation suite that
  scores earlier models retrospectively updates the frontier at the model's own
  date. This is what
  makes later revision of post-2023 values possible, and it is the semantics a
  capability-arrival measure needs.
- **Chain points.** All basket, series and membership changes take effect at a vintage's
  chain point (v2025: the 2023–2024 seam), never inside published history. This follows
  the convention of chain-linked official statistics: entry into the basket lags
  capability by construction, the bias direction is known and disclosed, and history is
  never backfilled with hindsight-selected benchmarks, which would overstate progress
  precisely where AI later succeeded.

## 3. How new series and subdomains enter

A series is admitted only with a complete declaration: scale (one of eight declared
families); a reference value where the series is used in any human-comparison reading
(anchor kinds: human, expert, instrument ceiling, ceiling by convention, parity by
construction; series that only feed progress may enter without one); an evaluation
protocol (`pure_model` or `system_level`, never mixed within a series); a chain year at
or after the current vintage's chain point; a stated licence or permission basis (where
scores are quoted from an organiser's publication, the basis is published facts with
citation); and provenance (source, retrieval date, file hashes).

An entrant's direct contribution is zero in its entry year, and it enters an
observed-member mean's denominator only from its first measured year, so admission
changes no composite value at the chain point. Automated checks verify on every assembly
that the protected window is cell-identical (all taxonomies, stored precision) and that
no admitted series carries a value before its chain point.

## 4. Vintage v2025 (release candidate; assembled August 2026, amended 4 September, revised 5 September 2026)

Until v1.1.0 is deposited, everything here describes the assembled release candidate.

**Sources for the appended years:** the recovered Papers with Code archive (2024 refresh
of surviving series) and Epoch AI's benchmark data (CC BY 4.0), both Epoch's own
standardised evaluation runs and its collected series.

**Series admitted at the 2024 chain point** (full declarations, reference values and
quoted evidence in `VINTAGES.md` and the shipped anchors file):

| Subdomain | Series | Protocol | Reference value | Licence / permission |
|---|---|---|---|---|
| Agentic task execution | METR task horizons, 80% reliability (primary) | system_level | 960 min, instrument ceiling | METR data with written permission (cite METR; not affiliated) |
| Agentic task execution | OSWorld | system_level | 72.36 (human) | CC BY 4.0 (Epoch collection) |
| Agentic task execution | GDPval | system_level | 50 (parity by construction: win rate vs human professionals) | CC BY 4.0 (Epoch collection) |
| Mathematical & scientific reasoning | GPQA Diamond (Epoch's own runs) | pure_model | 81.3 (expert accuracy) | CC BY 4.0 |
| Mathematical & scientific reasoning | MATH Level 5 | pure_model | 90 (expert; full-set figure, declared caveat) | CC BY 4.0 (Epoch collection) |
| Software engineering | SWE-bench Verified (Epoch's own runs) | system_level | 95, ceiling by convention | CC BY 4.0 |
| Conversation | Theory of Mind on ToMBench | pure_model | 86.1 (organiser human baseline) | MIT |
| Language comprehension & QA | SimpleBench | pure_model | 83.7 (organisers' human baseline, n=9, declared caveat) | scores quoted as published facts with citation (simple-bench.com) |

TheAgentCompany is carried as a corroboration series outside the basket (95, the ceiling by
the SWE-bench convention; fixed to one simulation environment so an environment change
is never booked as capability). The METR 50%-reliability variant was retired when
frontier systems outgrew its range; the two reliability bars are one construct and are
never in the basket together.

**Two new application areas with exposure columns** (`daioe_agentic`, `daioe_mathsci`),
built from the Felten-Raj-Seamans 2018 expert matrix's two technical-problem rows, used
unedited and checked for concordance by two independent LLM re-scorings from different
vendors, a consistency check rather than a validation of the rows for the new
constructs (details and the shipped run outputs in `VINTAGES.md`). Both columns are chained: no
values before 2024.

**Composite membership (amended 4 September 2026).** `daioe_genai` keeps its original
membership (language modelling and image generation) permanently. An earlier decision
to broaden its membership at the seam was withdrawn before deposit: under the raw-sum
construction, 99 per cent of the resulting 2025 step came from two newly admitted
members' thin-baseline first increments, a scale artefact rather than measured
generative progress. The broadened thematic composite is instead `daioe_g2gen`, built
the second-generation way (Section 5), where conversation and software engineering enter
in standardised units. A second-generation overall composite (`daioe_g2all`) is
published with a complete history of its own; the standardisation table ships as
`g2_sigma_v1.csv` and the constructions and checks are documented in `VINTAGES.md`.

**Known caveats:** (i) a newly admitted series' first measured year is computed against
its entry-year frontier, and where that baseline is thin, late-entry-year capability is
booked to the first measured year. The 2024 evaluation counts are SWE-bench
Verified 1, GDPval 1, OSWorld 2, ToMBench 2, METR-80 7, GPQA 7, SimpleBench 19,
MATH Level 5 52; the low-count cases' 2025 increments are upper bounds in a
precise sense (a frontier over fewer evaluations is weakly understated, so
retrospective scoring of 2024 models can only raise the baseline and shrink the
step); (ii) in 2025, four of the nine original applications are
unobserved (abstract strategy games, real-time video games, language modelling,
translation: reporting ended, series carried at their last level, outside the
observed-member means), while visual question answering is observed with a measured
zero increment (inside them); composite values ship with a coverage audit;
(iii) reference-value kinds are declared per series and recorded with quoted evidence
in the anchors file.

## 5. The five composites, and which to use

**`daioe_allapps`, the legacy overall index.** Raw-sum construction over the nine
original applications, permanently; the replication object behind the published
estimates. The construction has no denominator: each year's occupation-level
increment adds the ability-weighted contributions of the applications observed
that year, and an application with no source contributes zero. Appended
increments (2024 onward) are therefore understated, not rescaled, as sources
end; the coverage audit states which applications each year books at zero.

**`daioe_genai`, the legacy generative composite.** Raw-sum over its original two
members, language modelling and image generation, permanently. Use either legacy column
for continuity with the published measure.

**`daioe_g2all`, overall exposure, current.** Each application's annual progress in
units of its historical year-to-year variation, averaged over the applications observed
that year (equal weights: the object is average progress across domains, and weighting
by expert-matrix relevance mass instead reorders occupations imperceptibly); all
thirteen applications are eligible. This is what lets generative,
agentic and reasoning domains sit in one number, and it is the recommended headline for
current monitoring from 2024 onward, read with its composition in view: the four
applications in their first measured year jointly carry 72 per cent of 2025's
summed standardised progress, and the application-level mean 2025 increment is
1.15 with them and 0.59 without them, a range the release reports rather than
resolves (the shipped `daioe_g2nine` carries the second reading as a column). Not a constant-basket series. Every application's standard deviation blends its
own history with a scale-family prior in proportion to how much history it has
(shrinkage, the prior worth five years of pseudo-history; the released sigma
table states each application's components and weights), so a new application
starts on its family's typical variation and grows into its own smoothly, with
no threshold and no unit break. Where
the two overall indices overlap, within-year Spearman rank agreement across O*NET-SOC
occupations is 0.61 in the young 2013 cross-section, 0.95 by 2016 and 0.99 from
2023; cross-sections of cumulated indices agree near-mechanically, so the informative
diagnostics are the increment ones: per-year increment rank agreement is 0.94--1.00
throughout, and the occupation-mean increment paths correlate at 0.81 over 2013--2023
and 0.30 through 2025, the divergence arriving exactly where the new domains enter
and widening under the shrinkage standardisation, which gives them more weight.

**`daioe_g2gen`, generative exposure, current.** The same construction restricted to
the four generative applications (language modelling, image generation, conversation,
software engineering). The overall composite's rule that no single member may drive more than half of
a year's movement is not applied here. With only three or four members, a share
above one half is the expected outcome rather than a warning sign, so the rule
would stop every build while revealing nothing. Instead the release
documentation reports, year by year, how much each member contributed; in 2025
software engineering contributed 73 per cent of the generative composite's standardised sum, largely its first measured year against a thin baseline. Use it when the question is generative AI specifically. Within-year rank
agreement with `daioe_genai` (Spearman, O*NET-SOC occupations) is 0.97–0.99 from 2016
in levels; in increments it is 0.98–0.99 until 2025 and 0.89 in 2025, the first year
the two constructions genuinely differ.

**`daioe_g2nine`, the balanced composite.** A third second-generation
composite: the same standardised construction as `daioe_g2all`, restricted to
the nine original applications, with membership that never changes. Its
movement is therefore capability progress on the original basket and nothing
else, and the gap to `daioe_g2all` in any year is what the new domains
contribute. Use it to separate progress from composition.

**The two new subdomains.** `daioe_agentic` (autonomous multi-step execution of real
computer work, measured as the length of human task completed reliably) and
`daioe_mathsci` (graduate-level scientific and mathematical problem-solving) are
subdomain columns like `daioe_lngmod`, not composites. Both are chained at 2024 with no
earlier values, so their histories are short and their early movements rest on few
series: agentic on one primary series (METR), and mathematical and scientific
reasoning showing, with software engineering, the largest standardised 2025
increments of any application (each about 2.8 borrowed scale-family standard
deviations). The two magnitudes have different anatomies: software
engineering's rests on a one-evaluation 2024 baseline and is an upper bound,
while maths/science's rests on a seven-evaluation baseline and a genuine GPQA
surge, with the borrowed denominator the main uncertainty in both. The borrowed standard
deviations behind the standardised units matter for levels but not for ranks:
halving or doubling them moves the size of the 2025 composite increment by a
factor of roughly three while leaving occupation rankings essentially unchanged
(Spearman at least 0.995; `scripts/robustness_g2_sigma_prior.py` in the
repository).

## 6. Reading and rescaling the scores

The released panels are raw index values. The index has no natural units: a level or a
change is meaningful only relative to other occupation-years, and every estimate in the
paper standardises before use. Three presentation conventions cover most needs.

**Cross-sectional standing: percentile companions.** From v1.1.0 every `daioe_*` column
carries a tie-invariant midrank percentile (`pctl_mid_*`): identical substantive values
carry identical percentiles, and the reading is "at or above the midpoint of its tied
group relative to that year's occupations". The legacy `pctl_rank_*` columns remain the
published replication artefact, with a caveat: they are order-dependent inside tied
groups, so two occupations with identical scores can carry different ranks (up to whole
all-tie years). For v1.0.0, where only the legacy ranks exist, do not use ranks where
ties matter; the substantive columns are authoritative.

**Level and growth: rescale to the frozen-window peak.** For a cardinal reading, divide
by the panel's frozen-window maximum and multiply by 100. The denominator is computed
once, on the 2010–2023 rows only, and reused unchanged for later vintages:

```
peak = max(value where 2010 <= year <= 2023)   # once per taxonomy panel and column
score_rel_max = 100 * value / peak
```

The result reads "per cent of the most exposed occupation-year in the frozen window"
(that peak is a 2023 clerical cell in every panel: office clerks 4413 on ISCO-08,
mail clerks 43-9081 on the SOC panels, 2121 on the SSYK panels);
values above 100 read as exposure beyond the frozen-window peak. The transformation is
linear, so ratios and time paths survive. Never take each vintage's own maximum, which
would rescale history with every release. The same convention applies per sub-index,
each with its own frozen-window maximum; do not compare rescaled values across
sub-indices. **This convention does not apply to `daioe_agentic` and `daioe_mathsci`**, which have
no 2010–2023 history of their own: read them through their percentile companions or
in their own units, and treat any rescaling base as a choice to be stated. The
second-generation composites do carry full-window histories, but as columns new to
v1.1.0 those histories sit outside the freeze guarantee (Section 2), so state the
vintage when rescaling them.

**Estimation: standardise on frozen moments.** As in Section 2: 2010–2020 moments,
computed once, for the columns that have them.

We deliberately ship raw values rather than a rescaled column: the raw cells are the
citable layer the release checks protect and published work builds on, and one
canonical scale avoids version ambiguity.

## 7. Changelog

- **5 Sep 2026, revision 3 of the release candidate.** Shrinkage standard
  deviations replace the five-year rule (prior worth five years of
  pseudo-history; no threshold, no unit break); a balanced nine-member
  companion column (`daioe_g2nine`) is added; and a fresh Epoch retrieval
  verified that no 2024 frontier revises, so the thin-baseline caveat stands
  with a dated check.
- **5 Sep 2026, external-review hardening.** Three independent cold reviews of the
  public documents; every numeric claim they challenged is now computed and shipped
  as a robustness script (errata counterfactual, sigma-prior sensitivity, composite
  diagnostics), known biases of the appended years are stated with directions and
  magnitudes, and the concordance statistics were corrected to the shipped
  artefacts.
- **4 Sep 2026, composite-membership amendment.** The planned broadening of
  `daioe_genai` was withdrawn before deposit (99 per cent of the resulting 2025 step
  traced to two thin-baseline first increments under raw-sum aggregation); `daioe_genai`
  keeps its original membership permanently and `daioe_g2gen` carries the broadened
  thematic composite in standardised units. Sections 4 and 5 updated accordingly.
- **25 Aug 2026, §4 updated.** The 24 Aug admission round folded in: METR-80 primary
  agentic with OSWorld and GDPval; MATH Level 5; SimpleBench; TheAgentCompany moved to
  corroboration outside the basket; the two activated exposure columns and the
  second-generation composite documented; anchor kinds ratified. The 2024 refresh was
  rebuilt under the seam discipline the same day (frozen window verbatim, 2024 chained).
- **11 Aug 2026, rescaling guidance added** (now Section 6): the relative-to-peak
  transformation documented for users rather than shipped as a column.
- **Aug 2026, v2025 assembled** (release candidate): first vintage extending the
  window beyond 2023 with new application areas (the 2024 refresh, released with
  v1.0.0, appends a year without membership change); new series admitted at the 2024
  chain point; the automated checks and the coverage audit introduced.
- **2023–2024, the frozen 2010–2023 index**: the paper's series. The Stata
  construction was later ported to Python; a clean build reproduces every substantive
  cell at stored precision (documented residual classes in `VALIDATION.md`), while the
  legacy tie ordering of rank columns is preserved by restoring the deposited v1.0.0
  values rather than by regeneration.

What each released vintage contains, and why, is documented in [VINTAGES.md](VINTAGES.md).
