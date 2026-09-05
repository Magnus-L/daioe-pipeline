# DAIOE vintages

This file is the public record of what each vintage of the measure contains and why.
It ships inside each release bundle and lives at the head of the repository. The
paper and its online appendix document the frozen 2010–2023 index that every
published estimate uses; everything below concerns later vintages, and none of it
can change a frozen value: assembly stops rather than produce a vintage in which any
published 2010–2023 cell would differ (see "Provenance and verification" for the
exact scope of that guarantee).

Two units of count are used throughout and are not interchangeable: a **benchmark**
is a task (e.g. SWE-bench Verified); a **benchmark series** is one measured score
track on a benchmark (a benchmark can carry more than one, e.g. separate metrics or
splits). The frozen index has 140 benchmarks carrying 149 measured series.

## The frozen index (2010–2023), released as v1.0.0

The object behind the published estimates. Nine applications, 140 benchmarks (149
series), as documented in the paper's Online Appendix Section C. Released as v1.0.0
together with the 2024 refresh.

**Four transcription slips in the source workbook, and what they touch.** Checking
the source workbook against the original benchmark repositories found four
transcription slips among its 3,933 score rows. They are listed with evidence in
`errata_frozen_workbook_v1.csv`, shipped in the bundle, and were reported to the
workbook's author in July 2026. Two of them (E1, a translation score attached to
the wrong model; E3, a model-name typo with the correct value) never touch a
frontier, so they affect no number in any release. The other two are small: one
translation benchmark's 2018 BLEU recorded as 28.36 rather than 29.11, and ARC's
2023 score as 96.3 rather than the source's own revised 96.4. Both sit inside
published history. We have computed exactly what correcting them there would do
(`scripts/robustness_errata_counterfactual.py`): the translation application
mean for 2018 would rise by 5.0 per cent of its value and the language-QA mean
for 2023 by 1.0 per cent, and propagated through the occupation index no
occupation-year level moves by more than half a per cent of a within-year
standard deviation (rank correlation with the published series 0.999998).
Since every estimate in the paper standardises exposure on within-year spreads,
the corrections are numerically irrelevant to any published result. The
frozen series reproduces the paper, so all four rows are retained exactly as
published; holding revisions for a chain point is the same convention official
statistics apply to benchmark revisions.

The slips do not affect the appended years either. Neither benchmark has a
post-2023 observation anywhere near its frontier (the best 2024 ARC score in the
archive is 81.5 against a frontier of 96.3), so a corrected and an uncorrected
release are numerically identical in 2024 and 2025; verified against the shipped
frontier data, September 2026. The pipeline still ships the correction switch
(`apply_errata`, off in every build to date) so that a future full re-estimation,
for instance at a journal revision, can apply the corrections from a stated chain
point with the construction documented. The switch will not run on a
frozen-window build, and each erratum must match exactly one source row; either
violation stops the build.

## The 2024 refresh, released as v1.0.0

Appends 2024 to the frozen window from the recovered Papers with Code archive,
with the basket unchanged. The benchmark count rises from 140 to 143: three continuation
benchmarks enter image comprehension at the seam, successor tasks that carry an
existing construct forward after their predecessors' reporting ended. Application
membership is unchanged: the same nine applications, no new areas. Built under the seam discipline (rebuilt 25 Aug 2026): the 2010–2023
window is carried verbatim from the frozen files and verified identical cell by
cell, while the 2024 increment is chained on the frozen 2023
level and computed against the recovered archive's fuller frontier state, which is
what the archive's pre-2024 rows are for; they inform the frontier, never the
published levels.

## The 2025 vintage, forthcoming as v1.1.0 (not part of v1.0.0)

Everything in this section describes the v1.1.0 release candidate. It is assembled
and verified, but until v1.1.0 is deposited its details are provisional and
this section, not any deposited record, is where they may still change.

The vintage covers 2010–2025 with its level chain point at the 2023–2024 seam.
What it adds:

**Eight admitted benchmark series**, each with a declared source, scale, evaluation
protocol and licence, and, where the series is used in any human-comparison
reading, a documented reference value with quoted evidence. Series that only feed
progress may enter without a reference value, which is the frozen basket's own
standard (65 of its 149 series carried none). Reference values never enter the
index computation: exposure is built from benchmark frontier increments alone, and
the anchors support admission, human-comparison readings, and a robustness
transformation that is checked at assembly but is not part of any released vintage.

| Series | Application | Reference | Notes |
|---|---|---|---|
| METR task horizons (80% reliability) | Agentic task execution | 960 min, instrument ceiling | The primary agentic series: the length of real computer-based work task, in minutes of human working time, completed at 80% reliability. Fixed to version 1.1 of METR's task suite; used with METR's written permission of 13 Aug 2026 (cite METR; METR is not affiliated with this work), with the licence basis restated at each deposit per LICENSE-DATA and scripts/check_metr_licence.py. The suite's 50%-reliability variant was retired when frontier systems outgrew its 16-hour range; the two variants are one construct and are never in the basket together. |
| OSWorld | Agentic task execution | 72.36, human | Real desktop computer work; externally collected scores from heterogeneous system set-ups, declared as such. |
| GDPval | Agentic task execution | 50, parity by construction | Scored as a win rate against human professionals, so 50 is parity by definition. |
| TheAgentCompany | Agentic task execution | 95, ceiling (by convention) | Corroboration series, not in the basket: fixed to one simulation environment (results from other environments excluded so an environment change is never booked as capability); the ceiling follows the SWE-bench convention. |
| GPQA Diamond | Mathematical and scientific reasoning | 81.3, expert | Graduate-level science questions, "Google-proof" by design. |
| MATH Level 5 | Mathematical and scientific reasoning | 90, expert (full-set figure) | Competition mathematics; near-saturated, so it adds corroborating coverage rather than increment. The 90 is a full-set figure, not Level-5-specific: it is declared for provenance and is not usable for Level-5 parity readings; like every reference value it does not enter the index. |
| SWE-bench Verified | Software engineering | 95, ceiling (by convention) | Real GitHub issue resolution, human-screened task subset; scores from Epoch AI's own standardised evaluation runs. |
| ToMBench | Conversation | 86.1, human | Theory of mind through everyday social scenarios; organiser-published human baseline. |
| SimpleBench | Language comprehension and QA | 83.7, human (n=9, declared caveat) | Adversarial everyday reasoning; organisers' own runs on a private test set. |

(Nine rows because TheAgentCompany is carried as corroboration outside the basket.)
Anchor kinds are declared per row in the released anchors file, whose schema carries
scale, anchor value, anchor kind, category, source, quoted evidence, and a
verification status per row.

**Two new application areas with exposure columns.** Agentic task execution and
mathematical and scientific reasoning enter with their own occupation exposure
columns. Their ability-relevance rows come from the same expert matrix as every
other application: Felten, Raj and Seamans (2018) scored sixteen application areas,
and the two technical-problem rows serve the two new areas ("solving real-world
technical problems" for agentic task execution; "solving constrained,
well-specified technical problems" for mathematical and scientific reasoning),
used unedited. The borrowed rows were checked by an informal concordance exercise, an
independent LLM re-scoring of the expert matrix from definitions alone: held-out
r = 0.76 (Pearson; Spearman 0.77) across the matrix, the two rows themselves at
0.80 and 0.79, with a second, independently prompted model from a different vendor
agreeing (0.81 and 0.80 against the same expert rows; the runs and scores ship in
the repository at `mapping/output/frs_validation_published_v2018.json`, generator
`mapping/code/validate_against_frs.py`). We read this as a consistency check only, not as validation of the rows as occupational-ability
mappings for the new constructs; blinded human expert re-rating of the two new areas is declared
future work at a chain point. Conversation and software engineering use their
original expert rows. Both new columns are chained: they are missing (not zero)
before 2024 in every format, zero at the 2024 chain year, and cumulate from there.

**Composite membership (amended 4 September 2026).** `daioe_genai` keeps its
original membership permanently (language modelling and image generation), the
same way `daioe_allapps` keeps its nine applications: both are legacy columns
whose construction never changes. An earlier decision had broadened genai's
membership at the seam under its raw-sum construction; inspection of the
assembled candidate showed that 99 per cent of the resulting 2025 step (+1.546
of +1.564) came from the two newly admitted members' thin-baseline first
increments, an artefact of scale rather than a measurement of generative
progress, and the broadening was withdrawn before deposit. The thematic
broadened composite exists instead as `daioe_g2gen` below, in standardised
units, where newly admitted applications cannot dominate by scale. The two new
application areas are not members of either legacy composite, by design.

**A second-generation overall composite** (`daioe_g2all`) enters as an
additional column. The new areas arrive in different units: METR's agentic
series is measured in minutes of task length, most older benchmarks in
percentage points. Summing raw units would let the units, rather than the
progress, set the weights. The companion aggregate therefore removes scale
from the construction: each application's annual progress is divided by the
standard deviation of its own historical year-to-year changes, and the
composite is the mean over the applications observed that year. An application
observed for fewer than five years has no usable standard deviation of its
own, so it borrows the value estimated for benchmarks measured on the same
scale until its own history accumulates; the later switch to its own history
is prospective, revises no earlier level, and the released table
(`g2_sigma_v1.csv`) records each application's standard deviation, its basis
and the switch rule. The composite has values over the full 2010--2025 window.
Each year's mean runs over the applications observed that year (a measured
zero counts as observed; a year with no source does not), so early years have
few members (three in 2013) and 2025 runs on partial coverage (see the
caveats). It is therefore not a constant-basket series: a movement between
years can mix capability progress with a change in which applications are
observed, and should be read accordingly.

Two checks run on every assembly, and the assembly stops if either fails.
First, the composite must not depend on how the METR series is expressed: that
series can be stated in task minutes or as a percentage-style score, and
recomputing the composite the other way must move the 2025 increment by less
than 15 per cent (it moves it by 13.7). Second, no application may contribute
more than half of a year's summed standardised progress (the maximum observed
is 35 per cent); if one application out of thirteen drove more than half, the
likeliest explanation would be an error in its data or scale rather than
genuine progress, so the assembly stops for inspection instead of publishing.
The two thresholds are our choices, not estimates, and there is no field
standard to appeal to; we state the rationale for each instead. The one-half
rule takes the majority threshold as its focal point. The 15 per cent
tolerance was set at the composite's introduction just above the sensitivity
then measured and accepted, so its content is a no-deterioration rule: later
assemblies may not be more unit-dependent than the one inspected here. As with
a significance level, the particular magnitudes could have been otherwise;
what disciplines them is that they are fixed in advance, a failing assembly
cannot pass without a documented decision, and the measured values are
published beside them so the reader can see the slack. Within-year rank agreement with `daioe_allapps` is reported as a diagnostic
rather than enforced, since the two aggregates weight the basket differently
by design (Spearman over O*NET-SOC 2010 occupations, per year: 0.74 in the
three-member 2013 cross-section, 0.97 by 2016, 0.99 in 2023 and 2025). The
original all-applications composite continues unchanged.

**A second-generation generative composite** (`daioe_g2gen`) is the same
construction restricted to the four generative applications: language
modelling, image generation, conversation and software engineering. It uses the
same standard deviations and the same mean over observed members, and it equals
zero until its first members begin in 2012. The overall composite's more-than-half rule is not applied here: with at most
four members, and in a typical year three with data, a share above one half is
the expected outcome rather than a warning sign, so the rule would stop every
assembly while revealing nothing. We therefore replace the rule with
transparency: the release documentation reports, year by year, how much each
member contributed. In 2025 most of its movement comes from software
engineering's first measured year, computed against a thin baseline and best
read as an upper bound that later vintages will revise as more evaluations
accumulate. Within a year its ranking of occupations agrees closely with the
legacy generative composite (Spearman 0.97--0.99).

**Tie-invariant percentiles.** Every `daioe_*` column gains a `pctl_mid_*`
companion: the within-year midrank percentile (average rank of the tied group over
the number of non-missing occupations, times 100), so identical substantive values
carry identical percentiles and an all-tie year sits uniformly near 50 instead of
an arbitrary spread. The legacy `pctl_rank_*` columns are unchanged and remain the
published replication artefact; the new columns are outside the freeze claim, like
every column new to a vintage.

**Known caveats, shipped rather than filed.** A newly admitted series' first
increment is computed against its entry-year frontier; where that baseline is thin
(SWE-bench Verified: one 2024 evaluation; ToMBench: two), the 2025 increment is an
upper bound, revisable as evaluation suites score earlier models retrospectively.
The same caution applies to the borrowed standard deviations: halving or
doubling the scale-family values that the four young applications borrow moves
the size of the 2025 composite increment by a factor of roughly three in either
direction, while leaving occupation rankings essentially unchanged (Spearman at
least 0.995 across occupations, increments and levels alike;
`scripts/robustness_g2_sigma_prior.py`). The level of the 2025 step should
therefore be read as provisional, and cross-sectional comparisons of
occupations as robust. For 2025 the original basket splits three ways, and the distinction matters for
`daioe_g2all`'s denominator. Four applications are unobserved in 2025 (abstract
strategy games, real-time video games, language modelling, translation): their
sources' reporting ended, their series are carried at the last level, and they are
outside the 2025 G2 mean. Visual question answering is observed, with a measured
zero increment (its continuation source reported in 2025 and the frontier did not
move), so it is inside the 2025 G2 mean. The remaining originals and the new areas
are observed with measured progress. In every case it is the reporting that ended, not the capability, and 2025 is a partial-coverage year
for the original basket. Vintage values beyond
2023 are revisable in later vintages; the frozen window is not.

## Citing a vintage

v1.0.0 contains two objects, the frozen 2010--2023 index and the 2024 refresh, so
a bare version number is ambiguous. Cite the DOI plus the object name plus the
filename loaded (for example: ``DAIOE v1.0.0, frozen 2010--2023 index,
daioe_ssyk2012.dta''). From v1.1.0 each vintage adds one object and the same rule
applies.

## Provenance and verification

Every admitted series has a provenance record (`data/updates/provenance_*.json`)
naming its source, retrieval date and file hashes. Every reference value is in `human_anchors_v1.csv` (shipped in
the bundle) with its source and a quoted passage. Every vintage assembly
re-verifies, cell by cell, that all frozen published values are unchanged in every
occupational taxonomy, and that no admitted series carries a value before its chain
year; no vintage is released unless every one of these checks passes.

**The exact scope of the freeze guarantee.** The frozen object is the set of
2010–2023 rows and the v1.0.0 column set (occupation code, year, the `daioe_*`
index columns and their `pctl_rank_*` companions), together with SOC 2010's 68
inherited year-less rows, which the deposited v1.0.0 file carries and every later
vintage must carry with the same values; all compared cell by cell at stored
(single) precision. Later vintages may add columns; a new column's 2010–2023 values
(such as `daioe_g2all`'s) have no v1.0.0 counterpart and are outside the freeze
claim. The canonical frozen files are the five taxonomy publication panels of the
deposited v1.0.0 scores bundle (`daioe_onetsoc2010`, `daioe_soc2010`,
`daioe_isco08`, `daioe_ssyk2012`, `daioe_ssyk96`, Stata `.dta`); the TSV and Excel
files are derived from them and are covered through that derivation rather than
verified independently. File-level byte identity is not claimed and cannot hold for
files that gain rows or columns; where a release copies a file unmodified, its
checksum manifest says so.

**Percentile ranks and ties, stated for anyone who compares releases cell by cell
or regenerates them from code.** Percentile ranks are order-dependent inside tie groups (year
cross-sections where many occupations share an identical cumulative value, up to
entire all-tie years such as reading comprehension in 2013, where every
occupation's substantive value is the same and the ranks differ only by historical
row order). The frozen v1.0.0 files carry the original Stata ranks; a regeneration
from the pipeline assigns ties in its own deterministic order. Later vintages
restore the frozen window's `pctl_rank_*` values from the v1.0.0 release verbatim,
so the frozen window is cell-identical across vintages on the full v1.0.0 column
set, substantive and rank alike. Two consequences users should know: identical
substantive values can carry different ranks inside a tie group, so ranks should
not be used where ties matter (the substantive `daioe_*` columns are authoritative
and never depend on tie order, and from v1.1.0 every panel carries tie-invariant
`pctl_mid_*` companions); and a clean pipeline run from raw inputs reproduces
every substantive cell but not the legacy tie ordering; full reproduction of the
rank columns uses the deposited v1.0.0 artefact, by construction.
