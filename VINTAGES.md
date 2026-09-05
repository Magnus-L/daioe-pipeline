# DAIOE vintages

This file is the public record of what each vintage of the measure contains and why.
It ships inside each release bundle and lives at the head of the repository. The
paper and its online appendix document the frozen 2010–2023 index that every
published estimate uses; everything below concerns later vintages, and none of it
can change a frozen value: the assembly gates refuse to build a vintage in which any
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

**Known errata, retained by design.** An errata file
(`errata_frozen_workbook_v1.csv`, shipped in the bundle) lists four small
transcription discrepancies found when checking the source workbook against the
original repositories. The released frozen data keep them exactly as the paper
estimated them: the frozen series is a replication object, not a best-current-belief
series. The corrections are declared for a future chain point and no released
vintage has yet applied them. The applying mechanism ships with the pipeline
(`apply_errata`, off in every build to date): it corrects the source rows so that
post-seam increments are computed against the corrected frontier state, the splice
keeps every published level, and two fatal guards hold: the flag refuses a
frozen-window build, and every erratum must match exactly one source row. The
vintage that first switches it on will state the applied construction and a worked
example beside its numbers. Two of the four (E2, E4)
would create or move state-of-the-art frontiers if applied inside history, which is
why they wait for a seam.

## The 2024 refresh, released as v1.0.0

Appends 2024 to the frozen window from the recovered Papers with Code archive,
basket-faithfully. The benchmark count rises from 140 to 143: three continuation
benchmarks enter image comprehension at the seam, successor tasks that carry an
existing construct forward after their predecessors' reporting ended. Application
membership is unchanged: the same nine applications, no new areas. Built under the seam discipline (rebuilt 25 Aug 2026): the 2010–2023
window is carried verbatim from the frozen files, cell-identical at stored
precision and gate-verified, while the 2024 increment is chained on the frozen 2023
level and computed against the recovered archive's fuller frontier state, which is
what the archive's pre-2024 rows are for; they inform the frontier, never the
published levels.

## The 2025 vintage, forthcoming as v1.1.0 (not part of v1.0.0)

Everything in this section describes the v1.1.0 release candidate. It is assembled
and gate-verified, but until v1.1.0 is deposited its details are provisional and
this section, not any deposited record, is where they may still change.

The vintage covers 2010–2025 with its level chain point at the 2023–2024 seam.
What it adds:

**Eight admitted benchmark series**, each with a declared source, scale, evaluation
protocol and licence, and, where the series is used in any human-comparison
reading, a documented reference value with quoted evidence. Series that only feed
progress may enter without a reference value, which is the frozen basket's own
standard (65 of its 149 series carried none). Reference values never enter the
index computation: exposure is built from benchmark frontier increments alone, and
the anchors support admission, human-comparison readings, and a gated robustness
transform that is not part of any released vintage.

| Series | Application | Reference | Notes |
|---|---|---|---|
| METR task horizons (80% reliability) | Agentic task execution | 960 min, instrument ceiling | The primary agentic series: the length of real computer-based work task, in minutes of human working time, completed at 80% reliability. Pinned to METR-Horizon v1.1; used with METR's written permission of 13 Aug 2026 (cite METR; METR is not affiliated with this work), with the licence basis restated at each deposit per LICENSE-DATA and scripts/check_metr_licence.py. The suite's 50%-reliability variant was retired when frontier systems outgrew its 16-hour range; the two variants are one construct and are never in the basket together. |
| OSWorld | Agentic task execution | 72.36, human | Real desktop computer work; externally collected scores, mixed agent scaffolds, declared as such. |
| GDPval | Agentic task execution | 50, parity by construction | Scored as a win rate against human professionals, so 50 is parity by definition. |
| TheAgentCompany | Agentic task execution | 95, ceiling (by convention) | Corroboration series, not in the basket: pinned to one simulation environment (results from other environments excluded so an environment change is never booked as capability); the ceiling follows the SWE-bench convention. |
| GPQA Diamond | Mathematical and scientific reasoning | 81.3, expert | Graduate-level science questions, "Google-proof" by design. |
| MATH Level 5 | Mathematical and scientific reasoning | 90, expert (full-set figure) | Competition mathematics; near-saturated, so it adds corroborating coverage rather than increment. The 90 is a full-set figure, not Level-5-specific: it is declared for provenance and is not usable for Level-5 parity readings; like every reference value it does not enter the index. |
| SWE-bench Verified | Software engineering | 95, ceiling (by convention) | Real GitHub issue resolution, human-screened task subset; Epoch-run harness. |
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

**A second-generation generative composite** (`daioe_g2gen`) enters as an
additional column: the second-generation construction (next paragraph) restricted
to the four generative applications (language modelling, image generation,
conversation and software engineering). Same sigma table, same
mean-over-observed-members rule; the column is carried at zero until its first
members enter in 2012. Its member shares are described rather than gated: the
dominance cap applies from five observed members (the main composite's own
convention for young cross-sections), a threshold a four-member composite can
never reach, so for `daioe_g2gen` the cap never binds and per-year member
shares are reported in the release documentation instead, and its 2025 movement is
still carried mainly by software engineering's first chained increment, an upper
bound revisable as baselines back-fill. Within-year rank agreement with the
legacy genai column is 0.97–0.99.

**A second-generation overall composite** (`daioe_g2all`) enters as an additional
column. As new capability domains with different native scales enter the basket, a
companion aggregate is useful in which every application's annual progress is
expressed in units of its historical year-to-year variation and averaged over the
applications observed that year. Applications with fewer than five observed years
borrow their scale family's benchmark-increment variation until a declared
sigma-basis switch (a change of standardisation basis only, prospective, distinct
from the level chain point: it does not revise any pre-switch level, while
increments from the switch year onward, and hence the levels they cumulate into,
use the new basis); the released sigma table
states each application's basis and the switch rule. The composite has values over
the full 2010–2025 window; each year's mean runs over the applications observed
that year (an application with a measured zero increment counts as observed; one
with no source that year does not), so early years have few members (the 2013
cross-section has three) and 2025 runs on partial coverage (see the caveats).
Like the broadened generative composite, `daioe_g2all` is therefore not a
constant-basket time series: a movement between years can mix capability progress
with a change in which applications are observed, and should be read accordingly.
Two fatal bounds are checked on every build: a sensitivity bound on the axis
convention for the METR series (recomputing with METR on its percentage axis moves
the 2025 composite increment by 13.7%, against a pre-set bound of 15%), and a
dominance bound (no application's share of any chained year's summed standardised
progress may exceed one half; the maximum is 35%). Within-year rank agreement with
`daioe_allapps` is reported as a diagnostic rather than gated, since the two
aggregate the basket differently by design (Spearman over O*NET-SOC 2010
occupations, per year: 0.74 in the three-member 2013 cross-section, 0.97 by 2016,
0.99 in 2023 and 2025). The original all-applications composite continues
unchanged; the σ-table ships as `g2_sigma_v1.csv`.

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
upper bound, revisable as harnesses evaluate earlier models retrospectively. For 2025 the original basket splits three ways, and the distinction matters for
`daioe_g2all`'s denominator. Four applications are UNOBSERVED in 2025 (abstract
strategy games, real-time video games, language modelling, translation): their
sources' reporting ended, their series are carried at the last level, and they are
outside the 2025 G2 mean. Visual question answering is OBSERVED with a measured
zero increment (its continuation source reported in 2025 and the frontier did not
move), so it is inside the 2025 G2 mean. The remaining originals and the new areas
are observed with measured progress. In every case the archive's death is a
property of reporting, not of the capability, and 2025 is a partial-coverage year
for the original basket. Vintage values beyond
2023 are revisable in later vintages; the frozen window is not.

## Citing a vintage

v1.0.0 contains two objects, the frozen 2010--2023 index and the 2024 refresh, so
a bare version number is ambiguous. Cite the DOI plus the object name plus the
filename loaded (for example: ``DAIOE v1.0.0, frozen 2010--2023 index,
daioe_ssyk2012.dta''). From v1.1.0 each vintage adds one object and the same rule
applies.

## Provenance and verification

Every admitted series has a provenance sidecar (`data/updates/provenance_*.json`)
with content hashes. Every reference value is in `human_anchors_v1.csv` (shipped in
the bundle) with its source and a quoted passage. Every vintage assembly
re-verifies, cell by cell, that all frozen published values are unchanged in every
occupational taxonomy, and that no admitted series carries a value before its chain
year; no vintage is released without these gates green.

**The exact scope of the freeze guarantee.** The frozen object is the set of
2010–2023 rows and the v1.0.0 column set (occupation code, year, the `daioe_*`
index columns and their `pctl_rank_*` companions), together with SOC 2010's 68
inherited year-less rows, which the deposited v1.0.0 file carries and every later
vintage must carry with the same values; all compared cell by cell at stored
(single) precision. Later vintages may add columns; a new column's 2010–2023 values
(such as `daioe_g2all`'s) have no v1.0.0 counterpart and are outside the freeze
claim. The canonical frozen artefacts are the five taxonomy publication panels of the
deposited v1.0.0 scores bundle (`daioe_onetsoc2010`, `daioe_soc2010`,
`daioe_isco08`, `daioe_ssyk2012`, `daioe_ssyk96`, Stata `.dta`); the TSV and Excel
files are derived from them and are covered through that derivation rather than
gated independently. File-level byte identity is not claimed and cannot hold for
files that gain rows or columns; where a release copies a file unmodified, its
checksum manifest says so.

**Percentile ranks and ties, stated for anyone who diffs releases or regenerates
from code.** Percentile ranks are order-dependent inside tie groups (year
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
