# DAIOE — Technical Documentation

**Dynamic AI Occupational Exposure (DAIOE)** translates performance improvements
across public AI benchmarks into occupation-year exposure scores, separately for
AI subdomains and composites. This document is the public technical reference
for the measure and its vintages, updated with each release.

**Authority.** For the frozen 2010–2023 construction, the paper and its online
appendix are the description of record; where the appendix and the
implementation differ, the implementation is authoritative and the differences
are the documented residual classes in `VALIDATION.md`. For everything after
the frozen window, `VINTAGES.md` is the record.

*Maintained by the AI-Econ Lab (Örebro University / RATIO). Contact: see
ai-econlab.com.*

---

## 1. The measure in brief

DAIOE combines three ingredients. The first is annual AI progress per
application: state-of-the-art frontiers over public benchmarks, rescaled per
Felten et al. (2018) so that linear increases reflect exponential improvement.
The second is an application-to-ability relevance matrix. The third is O*NET
occupation ability profiles with a social-skill discount.

The construction order matters, and it includes one nonlinear step. Per
occupation and year, the ability-weighted exposure increment is discounted for
social intensity (socially intensive work resists automation, so equal
capability arrival exposes it less), **squared** (the paper's construction:
squaring stretches the distribution of increments so dispersion across
occupations grows as capabilities accumulate), scaled by a constant ten common
to every cell, and cumulated over years to the index level. The rationale for
each step is the paper's construction section; here we state what each does
and what it leaves invariant. Squaring preserves the ordering of increments within a year exactly, because
increments are non-negative. Two properties do not follow automatically, and we
check them rather than assume them: in principle the ordering of cumulated
levels could differ, and the timing of progress could matter, since the same
cumulative progress arriving in fewer, larger steps yields a higher level. In
the data neither has bite for the rankings the index is read through.
Occupation rankings of levels against an unsquared variant, in which neither
concern arises, stay at Spearman 0.97 or higher in every year, and the paper
reports the headline estimate re-run on the unsquared index (Online Appendix,
Section M). Composites aggregate at
the application level before this occupation-level chain.

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
members from 2024; granting them columns is a discretionary decision taken at
a chain point. A
third second-generation composite, `daioe_g2nine`, runs over the nine original
applications only (Section 5).

Panels are published for five occupational taxonomies (O*NET-SOC 2010,
SOC 2010, ISCO-08, SSYK 2012 and SSYK 96), each with per-year percentile
companions. One caution for Swedish users: the frozen SSYK panels store the
occupation key as a label fusing code and title ("0110 Officerare") while the
refresh panels store it numerically, which drops leading zeros; the shipped
`occupation_titles_ssyk.csv` carries canonical zero-padded codes and titles
for safe joins and readable lists. The v1.0.0 bundle additionally ships
`soc2018/daioe_panel_soc2018.dta`, a SOC 2018 panel export on the frozen window
in the pipeline's internal panel schema: exposure changes and cumulative
levels, each cumulative column with a tie-invariant midrank percentile
companion, outside the publication-format gating. The export also carries the
robotics series excluded from the index (`roe`), a seven-member non-generative
variant of the aggregate (`redux`), and comparator exposure measures from the
literature (Felten-Raj-Seamans, Webb, Eloundou et al., Frey-Osborne; sources
and terms in `LICENSE-DATA`); its headline cumulative column `exp_cumul`
corresponds to `daioe_allapps`.

## 2. Vintages

**The frozen window, 2010–2023, is the series estimated in the paper.** Its
protection is precise: every 2010–2023 cell of the v1.0.0 column set (the
`daioe_*` columns and their `pctl_rank_*` companions, plus SOC 2010's 68
inherited year-less rows: one row for each of 68 codes that appear nowhere
else in the panel, a property of the original construction's crosswalk,
retained verbatim) is verified cell-identical at stored precision on
every assembly. Values after 2023 are revisable in later vintages; columns new
to a vintage carry their own history and are outside this guarantee.

**The released panels are unstandardised.** Standardisation to frozen 2010–2020
moments happens at estimation, where the moments are computed once and reused,
so appending a vintage never rescales an estimated year. The window ends in
2020 so that the moments predate the estimation frontier and the 2021–2023
acceleration, keeping standardised coefficients in pre-shock units. Users who
standardise a later vintage themselves must compute moments on 2010–2020 only,
never on the full window.

**Vintages are labelled by coverage window** (*DAIOE v2025* covers 2010–2025,
for example) and are separate, citable objects.

**Year assignment.** A benchmark score is assigned to the year of the evaluated
model's release, not the year of the evaluation. An evaluation suite that
scores earlier models retrospectively therefore updates the frontier at the
model's own date. This is what makes later revision of post-2023 values
possible, and it is the semantics a capability-arrival measure needs.

**Chain points.** All basket, series and membership changes take effect at a
vintage's chain point (v2025: the 2023–2024 seam), never inside published
history. This follows the convention of chain-linked official statistics.
Entry into the basket lags capability by construction, the bias direction is
known and disclosed, and history is never backfilled with hindsight-selected
benchmarks, which would overstate progress precisely where AI later succeeded.

## 3. How new series and subdomains enter

A series is admitted only with a complete declaration. It must state a scale
(one of eight declared families); a reference value where the series is used in
any human-comparison reading (anchor kinds: human, expert, instrument ceiling,
ceiling by convention, parity by construction; series that only feed progress
may enter without one); an evaluation protocol (`pure_model` or `system_level`,
never mixed within a series); a chain year at or after the current vintage's
chain point; a stated licence or permission basis (where scores are quoted from
an organiser's publication, the basis is published facts with citation); and
provenance, meaning source, retrieval date and file hashes.

Admission is designed to move nothing at entry. An entrant's direct
contribution is zero in its entry year, and it enters an observed-member mean's
denominator only from its first measured year, so admission changes no
composite value at the chain point. Automated checks verify on every assembly
that the protected window is cell-identical (all taxonomies, stored precision)
and that no admitted series carries a value before its chain point.

## 4. Vintage v2025 (release candidate; assembled August 2026, amended 4 September, revised 5 September 2026)

Until v1.1.0 is deposited, everything here describes the assembled release
candidate.

**Sources for the appended years.** The recovered Papers with Code archive (the
2024 refresh of surviving series) and Epoch AI's benchmark data (CC BY 4.0),
both Epoch's own standardised evaluation runs and its collected series.

**Series admitted at the 2024 chain point.** Full declarations, reference
values and quoted evidence are in `VINTAGES.md` and the shipped anchors file.

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

TheAgentCompany is carried as a corroboration series outside the basket (95,
the ceiling by the SWE-bench convention; fixed to one simulation environment so
an environment change is never booked as capability). The METR 50%-reliability
variant was retired when frontier systems outgrew its range; the two
reliability bars are one construct and are never in the basket together.

**Two new application areas with exposure columns** (`daioe_agentic`,
`daioe_mathsci`). Both are built from the Felten-Raj-Seamans 2018 expert
matrix's two technical-problem rows, used unedited and checked for concordance
by two independent LLM re-scorings from different vendors, a consistency
check rather than a validation of the rows for the new constructs (details and
the shipped run outputs in `VINTAGES.md`). Both columns are chained: no values
before 2024.

**Composite membership (amended 4 September 2026).** `daioe_genai` keeps its
original membership (language modelling and image generation) permanently. An
earlier decision to broaden its membership at the seam was withdrawn before
deposit: under the raw-sum construction, 99 per cent of the resulting 2025 step
came from two newly admitted members' thin-baseline first increments, a scale
artefact rather than measured generative progress. The broadened thematic
composite is instead `daioe_g2gen`, built the second-generation way
(Section 5), where conversation and software engineering enter in standardised
units. Two further second-generation composites are published with complete
histories of their own: the overall `daioe_g2all` and the balanced
`daioe_g2nine`. The standardisation table ships as `g2_sigma_v2.csv`, and the
constructions and checks are documented in `VINTAGES.md`.

**Known caveats, with their numbers.** First, a newly admitted series' first
measured year is computed against its entry-year frontier, and where that
baseline is thin, late-entry-year capability is booked to the first measured
year. The 2024 evaluation counts are SWE-bench Verified 1, GDPval 1, OSWorld 2,
ToMBench 2, METR-80 7, GPQA 7, SimpleBench 19, MATH Level 5 52. The low-count
cases' 2025 increments are upper bounds in a precise sense: a frontier over
fewer evaluations is weakly understated, so retrospective scoring of 2024
models can only raise the baseline and shrink the step. Second, in 2025 four of
the nine original applications are unobserved (abstract strategy games,
real-time video games, language modelling, translation: reporting ended, series
carried at their last level, outside the observed-member means), while visual
question answering is observed with a measured zero increment, inside them;
composite values ship with a coverage audit. Third, reference-value kinds are
declared per series and recorded with quoted evidence in the anchors file.

## 5. The five composites, and which to use

Availability differs by version: v1.0.0 ships the two legacy composites and
the nine subdomain columns; the three second-generation composites, the two
new subdomain columns and the precomputed `pctl_mid_*` companions ship from
v1.1.0.

**`daioe_allapps`, the legacy overall index.** Raw-sum construction over the
nine original applications, permanently; the replication object behind the
published estimates. The construction has no denominator: each year's
occupation-level increment adds the ability-weighted contributions of the
applications observed that year, and an application with no source contributes
zero. Appended increments (2024 onward) are therefore understated, not
rescaled, as sources end; the coverage audit states which applications each
year books at zero.

**`daioe_genai`, the legacy generative composite.** Raw-sum over its original
two members, language modelling and image generation, permanently. Use either
legacy column for continuity with the published measure.

**`daioe_g2all`, overall exposure, current.** Each application's annual
progress is expressed in units of its historical year-to-year variation and
averaged over the applications observed that year; all thirteen applications
are eligible. The weights are equal by choice, not by omission: the object is
average progress across domains, and weighting by expert-matrix relevance mass
instead reorders occupations imperceptibly. This construction is what lets
generative, agentic and reasoning domains sit in one number, and it is the
recommended headline for current monitoring from 2024 onward.

Read it with its composition in view. The four applications in their first
measured year jointly carry 72 per cent of 2025's summed standardised
progress, and the application-level mean 2025 increment is 1.15 with them and
0.59 without them: a range the release reports rather than resolves, with the
shipped `daioe_g2nine` carrying the second reading as a column. It is not a
constant-basket series. Every application's standard deviation blends its own
history with a scale-family prior in proportion to how much history it has
(shrinkage, the prior worth five years of pseudo-history; the released sigma
table states each application's components and weights), so a new application
starts on its family's typical variation and grows into its own smoothly, with
no threshold and no unit break.

Where the two overall indices overlap, within-year Spearman rank agreement
across O*NET-SOC occupations is 0.61 in the young 2013 cross-section, 0.95 by
2016 and 0.99 from 2023. Cross-sections of cumulated indices agree
near-mechanically, however, so the informative diagnostics are the increment
ones: per-year increment rank agreement is 0.94–1.00 throughout, and the
occupation-mean increment paths correlate at 0.81 over 2013–2023 and 0.30
through 2025, the divergence arriving exactly where the new domains enter and
widening under the shrinkage standardisation, which gives them more weight.

**`daioe_g2gen`, generative exposure, current.** The same construction
restricted to the four generative applications: language modelling, image
generation, conversation and software engineering. Use it when the question is
generative AI specifically. The overall composite's rule that no single member
may drive more than half of a year's movement is not applied here: with only
three or four members, a share above one half is the expected outcome rather
than a warning sign, so the rule would stop every build while revealing
nothing. Instead the release documentation reports, year by year, how much
each member contributed; in 2025 software engineering contributed 73 per cent
of the generative composite's standardised sum, largely its first measured
year against a thin baseline. Within-year rank agreement with `daioe_genai`
(Spearman, O*NET-SOC occupations) is 0.97–0.99 from 2016 in levels; in
increments it is 0.98–0.99 until 2025 and 0.89 in 2025, the first year the two
constructions genuinely differ.

**`daioe_g2nine`, the balanced composite.** A third second-generation
composite: the same standardised construction as `daioe_g2all`, restricted to
the nine original applications, with membership that never changes. Its
movement is therefore capability progress on the original basket and nothing
else, and the gap to `daioe_g2all` in any year is what the new domains
contribute. Use it to separate progress from composition.

**The two new subdomains.** `daioe_agentic` (autonomous multi-step execution
of real computer work, measured as the length of human task completed
reliably) and `daioe_mathsci` (graduate-level scientific and mathematical
problem-solving) are subdomain columns like `daioe_lngmod`, not composites.
Both are chained at 2024 with no earlier values, so their histories are short
and their early movements rest on few series: agentic on one primary series
(METR), and mathematical and scientific reasoning showing, with software
engineering, the largest standardised 2025 increments of any application (each
about 2.8 borrowed scale-family standard deviations).

The two magnitudes have different anatomies. Software engineering's rests on a
one-evaluation 2024 baseline and is an upper bound; maths/science's rests on a
seven-evaluation baseline and a genuine GPQA surge, with the borrowed
denominator the main uncertainty in both. That denominator matters for levels
but not for ranks: halving or doubling the family component of the shrinkage
sigmas moves the size of the 2025 composite increment by a factor of roughly
3.5 while leaving occupation rankings essentially unchanged (Spearman at least
0.99; `scripts/robustness_g2_sigma_prior.py` in the repository).

## 6. Reading and rescaling the scores

The released panels are raw index values. The index has no natural units: a
level or a change is meaningful only relative to other occupation-years, and
every estimate in the paper standardises before use. Three presentation
conventions cover most needs.

**Cross-sectional standing: percentile companions.** From v1.1.0 every
`daioe_*` column carries a tie-invariant midrank percentile (`pctl_mid_*`).
Identical substantive values carry identical percentiles, and the reading is
"at or above the midpoint of its tied group relative to that year's
occupations". The legacy `pctl_rank_*` columns remain the published replication
artefact, with a caveat: they are order-dependent inside tied groups, so two
occupations with identical scores can carry different ranks, up to whole
all-tie years. For v1.0.0, where only the legacy ranks exist, do not use ranks
where ties matter; the substantive columns are authoritative, and the midrank
is one line to compute yourself:

```
pctl_mid = 100 * rank(value, method="average", within year) / count(within year)
```

**Rankings and top-N lists.** To list the most exposed occupations in a year,
sort on the substantive column itself (`daioe_allapps` for continuity with the
published measure, `daioe_g2all` for current monitoring), which is the
authoritative object, and use the midrank percentile whenever you want a
percentile to display. Both give the same list, since the percentile is a
transform of the same values; the midrank additionally makes ties visible, so
a shared tenth place shows as a shared percentile instead of an arbitrary
ordering. Never build such a list from the classical `pctl_rank_*` columns:
inside a tied group they order by historical row position, and a top-N cut
through a tie would include one occupation and exclude its equal on nothing
but that.

**Level and growth: rescale to the frozen-window peak.** For a cardinal
reading, divide by the panel's frozen-window maximum and multiply by 100. The
denominator is computed once, on the 2010–2023 rows only, and reused unchanged
for later vintages:

```
peak = max(value where 2010 <= year <= 2023)   # once per taxonomy panel and column
score_rel_max = 100 * value / peak
```

The result reads "per cent of the most exposed occupation-year in the frozen
window"; that peak is a 2023 cell in every panel (coding and proof-reading
clerks 4413 on ISCO-08, proofreaders and copy markers 43-9081 on the SOC
panels, and mathematicians and actuaries 2121 on the SSYK panels),
and values above 100 read as exposure beyond the frozen-window peak. The
transformation is linear, so ratios and time paths survive. Never take each
vintage's own maximum, which would rescale history with every release. The
same convention applies per sub-index, each with its own frozen-window
maximum; do not compare rescaled values across sub-indices.

**This convention does not apply to `daioe_agentic` and `daioe_mathsci`**,
which have no 2010–2023 history of their own: read them through their
percentile companions or in their own units, and treat any rescaling base as a
choice to be stated. The second-generation composites do carry full-window
histories, but as columns new to v1.1.0 those histories sit outside the freeze
guarantee (Section 2), so state the vintage when rescaling them.

**Estimation: standardise on frozen moments.** As in Section 2: 2010–2020
moments, computed once, for the columns that have them. To make this
foolproof, the bundle ships the moments themselves
(`standardisation_moments_v1.csv`: mean and standard deviation per taxonomy
and column, computed over the 2010–2020 rows), so standardising is one line
and cannot be done on the wrong window:

```
mean = mean(value where 2010 <= year <= 2020)   # once per taxonomy panel and column;
sd   = sd(value   where 2010 <= year <= 2020)   # shipped in standardisation_moments_v1.csv
z    = (value - mean) / sd
```

The file carries no rows for `daioe_agentic` and `daioe_mathsci`, which have
no 2010–2020 history; read those through their percentile companions instead.

We deliberately ship raw values rather than a rescaled column. The raw cells
are the citable layer the release checks protect and published work builds on,
and one canonical scale avoids version ambiguity.

## 7. Versions of this document

This reference is updated with each release, and changes are logged from the
first deposit onward: each Zenodo version carries the documentation that
describes it, and the repository history records the rest.

What each released vintage contains, and why, is documented in
[VINTAGES.md](VINTAGES.md).
