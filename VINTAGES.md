# DAIOE vintages

This file is the public record of what each vintage of the measure contains and
why. It ships inside each release bundle and lives at the head of the
repository; when the two copies differ, the copy inside a deposited bundle is
the record for that version and the repository head describes the forthcoming
one. The paper and its online appendix document the frozen 2010–2023 index that
every published estimate uses. Everything below concerns later vintages, and
none of it can change a frozen value: assembly stops rather than produce a
vintage in which any published 2010–2023 cell would differ (see "Provenance and
verification" for the exact scope of that guarantee).

**A few words used throughout, defined once.** A *benchmark* is a task (SWE-bench
Verified, for example); a *benchmark series* is one measured score track on a
benchmark, and a benchmark can carry more than one (separate metrics or splits).
The two counts are not interchangeable; the frozen index has 140 benchmarks
carrying 149 series. A *frontier* is the best score recorded on a series up to a
given year, and the index is built from year-to-year movements of frontiers. A
*vintage* is one released version of the whole dataset, labelled by the years it
covers. The *seam* is the join between the frozen window and the appended years
(here, between 2023 and 2024), and a *chain point* is a seam at which changes of
membership or method are allowed to take effect; nothing changes inside
published history. A series is *chained* at a year when it enters with the value
zero there and accumulates onward, so that its arrival moves nothing at entry.

## The frozen index (2010–2023), released as v1.0.0

The object behind the published estimates. Nine applications, 140 benchmarks
(149 series), as documented in the paper's Online Appendix Section C. Released
as v1.0.0 together with the 2024 refresh.

**Four transcription slips in the source workbook, and what they touch.**
Checking the source workbook against the original benchmark repositories found
four transcription slips among its 2,108 score rows. They were reported to the
workbook's author in July 2026 and are listed with evidence in
`errata_frozen_workbook_v1.csv`, shipped in the bundle.

Two of the four never touch a frontier and therefore affect no number in any
release: E1 is a translation score attached to the wrong model, and E3 is a
model-name typo with the correct value. The other two are small. One translation
benchmark's 2018 BLEU score reads 28.36 where the source says 29.11, and ARC's
2023 score reads 96.3 where the source's own revision says 96.4. Both sit
inside published history, and we have computed exactly what correcting them
there would do: the translation application mean for 2018 would rise by 5.0 per
cent of its value, the language-QA mean for 2023 by 1.0 per cent, and once
propagated through the occupation index no occupation-year level moves by more
than half a per cent of a within-year standard deviation (rank correlation with
the published series 0.999998). Every estimate in the paper works in standardised units and reads effect
sizes against within-year spreads, so the corrections are numerically
irrelevant to any published result. The computation ships as
`scripts/robustness_errata_counterfactual.py`.

The frozen series exists to reproduce the paper, so all four rows are retained
exactly as published. Holding revisions for a chain point is the same convention
official statistics apply to benchmark revisions. The slips do not affect the
appended years either: neither benchmark has a post-2023 observation anywhere
near its frontier (the best 2024 ARC score in the archive is 81.5 against a
frontier of 96.3), so a corrected and an uncorrected release are numerically
identical in 2024 and 2025, verified against the shipped frontier data in
September 2026.

The corrections are committed, not merely available. The pipeline ships a
correction switch (`apply_errata`, off in every build to date) so that a future
full re-estimation, for instance at a journal revision, can apply them from a
stated chain point with the construction documented; that completes the analogy
with a scheduled benchmark revision. Two safeguards apply: the switch will not
run on a frozen-window build, and each erratum must match exactly one source
row. Either violation stops the build.

## The 2024 refresh, released as v1.0.0

Appends 2024 to the frozen window from the recovered Papers with Code archive,
with application membership unchanged: the same nine applications, no new
areas. The benchmark basket grows from 140 to 143. Three continuation
benchmarks enter image comprehension at the seam (Visual Genome pairs, Visual
Genome subjects, Visual7W): successor tasks that carry an existing construct
forward after their predecessors' reporting ended. All three come from the same
archive as the rest of the refresh, on the Percentage-correct scale, scored on
the pure-model protocol, and feeding progress only, so no reference value is
required; their provenance is the archive's own, in the shipped
`provenance/pwc_provenance.csv`.

The refresh was rebuilt on 25 August 2026 under the seam discipline. The
2010–2023 window is carried verbatim from the frozen files and verified
identical cell by cell. The 2024 increment is chained on the frozen 2023 level
and computed against the recovered archive's fuller record of where each
frontier stood; the archive's pre-2024 rows inform that frontier state and
never the published levels.

One consequence of that design is measurable, and we disclose it. Where the
archive shows a higher 2023 frontier than the frozen files, the capability in
that wedge is booked to neither year: not to 2023, which is frozen, and not to
2024, whose increment starts from the higher frontier. The wedge exists on two
of the 27 continuing series (one image-classification metric, 0.18 in
transformed units; one language-QA metric, 0.02). It is a one-off
understatement at the seam, in the same direction as the entry-lag bias
already disclosed.

## The 2025 vintage, forthcoming as v1.1.0 (not part of v1.0.0)

Everything in this section describes the v1.1.0 release candidate, currently at
revision 3 (5 September 2026: shrinkage standard deviations replace the
five-year rule, a balanced nine-member composite column is added, and a fresh
Epoch retrieval verified that no 2024 frontier revises, so the thin-baseline
caveat stands as stated). The candidate is assembled and verified, but until
v1.1.0 is deposited its details are provisional, and this section rather than
any deposited record is where they may still change.

The vintage covers 2010–2025 with its level chain point at the 2023–2024 seam.
It adds three things: eight admitted benchmark series, two new application
areas with their own columns, and three second-generation composites.

### Eight admitted benchmark series

Each admitted series comes with a declared source, scale, evaluation protocol
and licence, and, where the series is used in any human-comparison reading, a
documented reference value with quoted evidence. Series that only feed progress
may enter without a reference value; that is the frozen basket's own standard,
where 65 of the 149 series carried none. Reference values never enter the index
computation. Exposure is built from benchmark frontier increments alone; the
reference values (anchors) support admission decisions, human-comparison
readings, and one alternative construction, the anchored capability transform
(an information-weighted variant designed 7 August 2026), which is computed as
a robustness check at assembly and is not part of any released vintage.

| Series | Application | Reference | Notes |
|---|---|---|---|
| METR task horizons (80% reliability) | Agentic task execution | 960 min, instrument ceiling | The primary agentic series: the length of real computer-based work task, in minutes of human working time, completed at 80% reliability. Fixed to version 1.1 of METR's task suite; used with METR's written permission of 13 Aug 2026 (cite METR; METR is not affiliated with this work), with the licence basis restated at each deposit per LICENSE-DATA and scripts/check_metr_licence.py. The suite's 50%-reliability variant was retired when frontier systems outgrew its 16-hour range; the two variants are one construct and are never in the basket together. The 80% variant's best observed value is 186 minutes against the 960-minute ceiling, and when it saturates in its turn the same rule applies: a successor reliability bar enters at a chain point. |
| OSWorld | Agentic task execution | 72.36, human | Real desktop computer work; externally collected scores from heterogeneous system set-ups, declared as such. |
| GDPval | Agentic task execution | 50, parity by construction | Scored as a win rate against human professionals, so 50 is parity by definition. |
| TheAgentCompany | Agentic task execution | 95, ceiling (by convention) | Corroboration series, not in the basket: fixed to one simulation environment (results from other environments excluded so an environment change is never booked as capability); the ceiling follows the SWE-bench convention. |
| GPQA Diamond | Mathematical and scientific reasoning | 81.3, expert | Graduate-level science questions, "Google-proof" by design. |
| MATH Level 5 | Mathematical and scientific reasoning | 90, expert (full-set figure) | Competition mathematics; near-saturated, so it adds corroborating coverage rather than increment. The 90 is a full-set figure, not Level-5-specific: it is declared for provenance and is not usable for Level-5 parity readings; like every reference value it does not enter the index. |
| SWE-bench Verified | Software engineering | 95, ceiling (by convention) | Real GitHub issue resolution, human-screened task subset; scores from Epoch AI's own standardised evaluation runs. |
| ToMBench | Conversation | 86.1, human | Theory of mind through everyday social scenarios; organiser-published human baseline. |
| SimpleBench | Language comprehension and QA | 83.7, human (n=9, declared caveat) | Adversarial everyday reasoning; organisers' own runs on a private test set. |

(Nine rows because TheAgentCompany is carried as corroboration outside the
basket.) Anchor kinds are declared per row in the released anchors file, whose
schema carries scale, anchor value, anchor kind, category, source, quoted
evidence, and a verification status per row.

### Two new application areas with exposure columns

Agentic task execution and mathematical and scientific reasoning enter with
their own occupation exposure columns. Their ability-relevance rows come from
the same expert matrix as every other application: Felten, Raj and Seamans
(2018) scored sixteen application areas, and two of their technical-problem
rows serve the two new areas, used unedited ("solving real-world technical
problems" for agentic task execution; "solving constrained, well-specified
technical problems" for mathematical and scientific reasoning).

We checked the borrowed rows with an informal concordance exercise: a language
model re-scored the sixteen-row expert matrix from the definitions alone, and
we compared its answers with the experts'. Across the matrix the held-out
agreement is r = 0.78 (Pearson; Spearman 0.79), and the two borrowed rows
themselves score 0.80 (agentic) and 0.79 (maths/science). A second,
independently prompted model from a different vendor agrees: 0.81 and 0.80
against the same expert rows, and 0.92/0.91 with the first model. One caveat
belongs to both runs: the models were plausibly trained on the published 2018
matrix, so "from the definitions alone" constrains the prompt, not the models'
prior exposure. We therefore read the exercise as a consistency check only, not
as validation of the rows as occupational-ability mappings for the new
constructs, and blinded human expert re-rating of the two new areas is declared
future work at a chain point. (Files: the first model's run in
`mapping/output/frs_validation_claude_v2026_13apps.json`, generator
`mapping/code/validate_against_frs.py`; the same generator's re-scoring of the
published nine-row matrix alone gives held-out 0.69/0.74, in
`frs_validation_published_v2018.json`; the second vendor's record and raw
scores in `mapping/output/frs_crossvendor_chatgpt_2026-08-24.md` and the CSV
beside it.)

Conversation and software engineering use their original expert rows. Both new
columns are chained: missing (not zero) before 2024 in every format, zero at
the 2024 chain year, and cumulating from there. The pre-history convention
differs by object on one rule. A subdomain column is missing before its
construct is measured, because a zero there would assert a level for something
never observed; a composite is defined (at zero) wherever its formula has
members, because its zero reads "no measured progress on any member yet" and
keeps cumulation well defined from the panel start. This is why `daioe_g2gen`
carries zeros in 2010–2011 and values from 2012.

### Composite membership (amended 4 September 2026)

`daioe_genai` keeps its original membership permanently: language modelling and
image generation, the same way `daioe_allapps` keeps its nine applications.
Both are legacy columns whose construction never changes.

An earlier decision had broadened genai's membership at the seam under its
raw-sum construction. Inspection of the assembled candidate showed that 99 per
cent of the resulting 2025 step (+1.546 of +1.564) came from the two newly
admitted members' thin-baseline first increments: an artefact of scale, not a
measurement of generative progress. The broadening was withdrawn before
deposit. The thematic broadened composite exists instead as `daioe_g2gen`
below, in standardised units, where newly admitted applications cannot dominate
by scale. The two new application areas are not members of either legacy
composite, by design.

### The three second-generation composites

**Why they exist.** The new areas arrive in different units: METR's agentic
series is measured in minutes of task length, most older benchmarks in
percentage points. Summing raw units would let the units, rather than the
progress, set the weights. The second-generation composites therefore remove
scale from the construction: each application's annual progress is divided by
the standard deviation of its own historical year-to-year changes (its typical
annual step), and the composite is the mean over the applications observed that
year.

**Equal weights are a choice, not an absence of one.** The composite's object
is average progress across capability domains, so each domain counts once. The
natural alternative, weighting each application by the ability-relevance mass
it carries in the expert matrix, reorders occupations imperceptibly (increment
rankings identical at Spearman 1.000, levels 0.97–0.99;
`scripts/robustness_composite_diagnostics.py`), so the choice of weights does
not drive the cross-section.

**The standard deviations blend own history with a family prior.** A new
application has no history from which to estimate its typical annual step, so
every application's standard deviation is a credibility-weighted blend of its
own history and a scale-family prior: sigma = (n x own SD + 5 x family SD) /
(n + 5), where n is the application's observed 2010–2023 history and the prior
is the standard deviation of positive frontier increments, pooled over all
benchmarks sharing its measurement scale, positive only because a year in
which a frontier does not move says nothing about the size of a typical step
when one occurs (0.392 for the percentage-correct family; 0.835 for the score
family, which the agentic series takes). The prior
carries the weight of five pseudo-years: our choice, made where an earlier
rule had demanded five years of history before trusting an application's own
variation at all, and close to immaterial, since halving or doubling the
weight moves the 2025 composite increment by about five per cent either way,
whereas the prior's value is what matters
(`scripts/robustness_g2_sigma_prior.py` varies both). The blend replaces the
old cliff: it is continuous in n, has no unit break at any threshold, and also
damps the reward that pure own-history standardisation gives to unusually
smooth series. A new application with no history takes its
family prior exactly and grows into its own history smoothly at later chain
points. The released table (`g2_sigma_v2.csv`, generated by
`scripts/build_g2_v2_20260905.py`) records each application's standard
deviation, its components and weights. The table is versioned and frozen as
shipped; any re-estimation is itself a declared change at a chain point, never
a silent one. One distinction matters here: unlike the two assembly checks
below, which stop a build and never enter a released number, these standard
deviations sit inside every second-generation value. They are construction
parameters, and their sensitivity is quantified in the caveats.

**Coverage varies by year, and the composites say so.** The overall composite
has values over the full 2010–2025 window. Each year's mean runs over the
applications observed that year (a measured zero counts as observed; a year
with no source does not), so early years have few members (three in 2013) and
2025 runs on partial coverage (see the caveats). It is therefore not a
constant-basket series: a movement between years can mix capability progress
with a change in which applications are observed, and should be read
accordingly.

**The count behind "thirteen".** The composites draw on the nine original
applications, the two new areas with their own columns, and conversation and
software engineering, which enter as measured members from 2024 but carry no
subdomain columns of their own. Granting them columns is a discretionary
decision taken at a chain point, not an automatic threshold; the release keeps
the published paper's column set plus the two new areas.

**`daioe_g2all`, the overall composite**, runs over all thirteen applications.
Within-year rank agreement with `daioe_allapps` is reported as a diagnostic
rather than enforced, since the two aggregates weight the basket differently by
design (Spearman over O*NET-SOC 2010 occupations, per year: 0.61 in the young
2013 cross-section, 0.95 by 2016, 0.99 in 2023, 0.99 in 2025). The original
all-applications composite continues unchanged.

**`daioe_g2gen`, the generative composite**, is the same construction
restricted to the four generative applications: language modelling, image
generation, conversation and software engineering. It uses the same standard
deviations and the same mean over observed members, and it equals zero until
its first members begin in 2012. The overall composite's more-than-half rule
(below) is not applied here: with at most four members, and in a typical year
three with data, a share above one half is the expected outcome rather than a
warning sign, so the rule would stop every assembly while revealing nothing. We
therefore replace the rule with transparency: the release documentation
reports, year by year, how much each member contributed. In 2025 most of its
movement comes from software engineering's first measured year, computed
against a thin baseline and best read as an upper bound that later vintages
will revise as more evaluations accumulate. Within a year its ranking of
occupations agrees closely with the legacy generative composite (Spearman
0.97–0.99).

**`daioe_g2nine`, the balanced composite**, is the same construction restricted
to the nine original applications. Unlike the other composites its membership
never changes, so a movement in `daioe_g2nine` is capability progress on the
original basket and nothing else, and the gap between `daioe_g2all` and
`daioe_g2nine` in a year is exactly what the new domains contribute. Use it to
separate progress from composition at a glance.

### Two checks on every assembly

Both checks stop the assembly if they fail; neither enters any released number.

**First, the composite must not depend on how the METR series is expressed.**
The released construction takes the series in log minutes of task length,
because that measures the construct in its own units (how long a task the
system completes) and stays independent of the suite's instrument ceiling; the
alternative expresses it as a share of that 960-minute ceiling, which builds
the instrument's range into every increment.
Recomputing the composite the other way must move the 2025 increment by less
than 15 per cent. Under the shipped construction it moves it by 14.8: 0.997 on
the log-minutes axis against 0.849 on the share axis, so the shipped figure is
the higher of the two and the band is published rather than hidden in a
pass/fail line.

**Second, no single application may dominate a chained year.** On the chained
years (2024 onward), no application may contribute more than half of a year's
summed standardised progress; the maximum observed is 27 per cent
(mathematical and scientific reasoning, 2025). The logic is diagnostic: if one
application out of thirteen drove more than half, the likeliest explanation
would be an error in its data or scale rather than genuine progress, so the
assembly stops for inspection instead of publishing. The rule does not police
the pre-2024 history, where young cross-sections make dominance unremarkable;
those years are protected by the freeze instead. The check report
(`reports/g2v2_20260905/G2V2-REPORT.md`) is the audit trail for both bounds.

**Where the two thresholds come from.** They are our choices, not estimates,
and there is no field standard to appeal to; we state the rationale for each
instead. The one-half rule takes the majority threshold as its focal point. The
15 per cent tolerance was fixed at the composite's introduction, when the
measured sensitivity was 13.7 per cent; the shrinkage rebuild measures 14.8,
still inside the bound, and both readings are published with the band rather
than reduced to a pass/fail line. As with a significance level, the particular
magnitudes could have been otherwise. What disciplines them is that they are
fixed in advance, a failing assembly cannot pass without a documented decision,
and the measured values are published beside them so the reader can see the
slack.

### Tie-invariant percentiles

Every `daioe_*` column gains a `pctl_mid_*` companion: the within-year midrank
percentile (average rank of the tied group over the number of non-missing
occupations, times 100). Identical substantive values then carry identical
percentiles, and an all-tie year sits uniformly near 50 instead of an arbitrary
spread. The legacy `pctl_rank_*` columns are unchanged and remain the published
replication artefact; the new columns are outside the freeze claim, like every
column new to a vintage.

### Known caveats, shipped rather than filed

Four things a user of the appended years should know, each with its number.

**Thin entry baselines.** A newly admitted series' first increment is computed
against its entry-year frontier. The 2024 evaluation counts are: SWE-bench
Verified 1, GDPval 1, OSWorld 2, ToMBench 2, METR-80 7, GPQA Diamond 7,
SimpleBench 19, MATH Level 5 52. Where the count is low, the 2025 increment is
an upper bound in one precise sense: a frontier taken over fewer evaluations is
weakly understated, so later retrospective scoring of 2024-released models can
only raise the 2024 baseline and shrink the 2025 step. Software engineering and conversation are the two applications whose entire
2024 baseline is a single series with one and two evaluations respectively;
their 2025 increments carry this caveat with full force.

**Entrant weight in the 2025 composites.** The four applications in their first
measured year (conversation, software engineering, agentic, maths/science)
jointly carry 72 per cent of 2025's summed standardised progress. With them the
application-level mean 2025 increment is 1.15; without them it is 0.59. The
honest reading of the 2025 step is that range rather than either endpoint, and
`daioe_g2nine` is the shipped column for the second reading
(`scripts/robustness_composite_diagnostics.py`). The principle separating this
from the withdrawn genai broadening: there, the raw-sum construction let the
entrants' arbitrary units misstate the composite, a defect of construction;
here, the units are standardised and the remaining uncertainty is timing, which
is bounded, disclosed and revisable. Member contributions by chained year:

| Share of summed standardised progress | 2024 | 2025 |
|---|---|---|
| speech recognition | 27% | 0% |
| visual question answering | 21% | 0% |
| language modelling | 20% | unobserved |
| reading comprehension | 13% | 21% |
| generating images | 13% | 7% |
| image recognition | 6% | 0% |
| conversation | entry year | 3% |
| software engineering | entry year | 27% |
| agentic task execution | entry year | 15% |
| maths/science reasoning | entry year | 27% |

**What a missing year means, in both conventions.** The release handles a
series with no source in a year in two ways, and they bracket the truth from
opposite sides. The legacy columns carry a dead series at its last level, which
books zero progress: `daioe_allapps` and the subdomain columns are therefore
biased downward from 2024 as sources end, and the legacy generative composite
is nearly flat in 2025 (increment +0.02 at the occupation mean) because
language modelling, one of its two members, is unobserved that year. The
second-generation composites instead drop the unobserved application from that
year's mean, which implicitly credits it with the average progress of the
observed members; because series tend to die when saturated, the survivors are
disproportionately still-moving, so this convention leans upward. The practical
consequence for 2025 cross-sections: occupations loaded on agentic, software
and maths/science are measured toward the top of their plausible range, and
occupations loaded on language modelling and translation toward the bottom. The
remedy is replacement, not imputation: a dead construct re-enters when a
successor series carrying the same construct is admitted at a chain point (the
image-comprehension continuations are the precedent), and evaluating successor
series for language modelling and translation is first on the v2026 workplan.
This mirrors price-index practice, where carrying a missing price forward is
discouraged precisely because it biases measured change toward zero.

**The family priors inside the standard deviations.** Halving or doubling the
scale-family component of the shrinkage sigmas moves the size of the 2025
composite increment by a factor of roughly 3.5 in either direction (the four
entrants' sigmas are pure prior), while leaving occupation rankings essentially
unchanged (Spearman at least 0.99 across occupations, increments and levels
alike; `scripts/robustness_g2_sigma_prior.py`). Read the level of the 2025 step
as provisional and cross-sectional comparisons as robust. The same conclusion
holds for the paper's own squaring step (within-year orderings unchanged by
construction; cumulative-level rankings at Spearman 0.97 or higher against an
unsquared variant) and for the choice of expert row behind the two new columns
(swapping the two borrowed rows moves their 2025 occupation rankings by less
than half a Spearman point: 0.996).

**How 2025 splits, in one place.** Four applications are unobserved in 2025
(abstract strategy games, real-time video games, language modelling,
translation); visual question answering is observed with a measured zero
increment, so it stays inside the G2 mean; the remaining originals and the new
areas are observed with measured progress. In every case it is the reporting
that ended, not the capability, and 2025 is a partial-coverage year for the
original basket. Vintage values beyond 2023 are revisable in later vintages;
the frozen window is not. Because the two overall composites weight the basket
differently by design, their agreement is also a time-series question, not only
a cross-sectional one. The occupation-mean annual increments of `daioe_allapps`
and `daioe_g2all` correlate at 0.81 over 2013–2023 and 0.30 through 2025, the
divergence arriving exactly where the new domains enter and widening under the
shrinkage sigmas, which give the entrants more weight. Per-year increment rank
agreement across occupations is 0.94–1.00 throughout; for the generative pair
it is 0.98–0.99 until 2025 and 0.89 in 2025, the first year the two
constructions genuinely differ.

## Citing a vintage

v1.0.0 contains two objects, the frozen 2010–2023 index and the 2024 refresh,
so a bare version number is ambiguous. Cite the DOI plus the object name plus
the filename loaded (for example: "DAIOE v1.0.0, frozen 2010–2023 index,
daioe_ssyk2012.dta"). From v1.1.0 each vintage adds one object and the same
rule applies.

## Provenance and verification

Every admitted series has a provenance record naming its source, retrieval date
and file hashes (`data/updates/provenance_*.json` in the repository, which is
the audit surface for admissions; the scores bundle carries the archive-level
`provenance/pwc_provenance.csv`). Every reference value is in
`human_anchors_v1.csv`, shipped in the bundle, with its source and a quoted
passage. Every vintage assembly re-verifies, cell by cell, that all frozen
published values are unchanged in every occupational taxonomy, and that no
admitted series carries a value before its chain year. No vintage is released
unless every one of these checks passes.

**The exact scope of the freeze guarantee.** The frozen object is the set of
2010–2023 rows and the v1.0.0 column set (occupation code, year, the `daioe_*`
index columns and their `pctl_rank_*` companions), together with SOC 2010's 68
inherited year-less rows (a property of the original construction's crosswalk:
one row for each of 68 SOC 2010 codes that appear nowhere else in the panel,
carried with no year value and retained verbatim for replication), which the
deposited v1.0.0 file carries and every later vintage must carry with the same
values; all compared cell by cell at
stored (single) precision. Later vintages may add columns, and a new column's
2010–2023 values (such as `daioe_g2all`'s) have no v1.0.0 counterpart, so they
sit outside the freeze claim. The canonical frozen files are the five taxonomy
publication panels of the deposited v1.0.0 scores bundle (`daioe_onetsoc2010`,
`daioe_soc2010`, `daioe_isco08`, `daioe_ssyk2012`, `daioe_ssyk96`, Stata
`.dta`); the TSV and Excel files are derived from them and are covered through
that derivation rather than verified independently. File-level byte identity is
not claimed and cannot hold for files that gain rows or columns; where a
release copies a file unmodified, its checksum manifest says so.

**Percentile ranks and ties, stated for anyone who compares releases cell by
cell or regenerates them from code.** Percentile ranks are order-dependent
inside tie groups: year cross-sections where many occupations share an
identical cumulative value, up to entire all-tie years such as reading
comprehension in 2013, where every occupation's substantive value is the same
and the ranks differ only by historical row order. The frozen v1.0.0 files
carry the original Stata ranks; a regeneration from the pipeline assigns ties
in its own deterministic order. Later vintages restore the frozen window's
`pctl_rank_*` values from the v1.0.0 release verbatim, so the frozen window is
cell-identical across vintages on the full v1.0.0 column set, substantive and
rank alike. Two consequences follow for users. Identical substantive values can
carry different ranks inside a tie group, so ranks should not be used where
ties matter; the substantive `daioe_*` columns are authoritative and never
depend on tie order, and from v1.1.0 every panel carries tie-invariant
`pctl_mid_*` companions. And a clean pipeline run from raw inputs reproduces
every substantive cell but not the legacy tie ordering; full reproduction of
the rank columns uses the deposited v1.0.0 artefact, by construction.
