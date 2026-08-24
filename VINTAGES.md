# DAIOE vintages

This file is the public record of what each vintage of the measure contains and why.
It travels with the released data. The paper and its online appendix document the
frozen 2010–2023 index that every published estimate uses; everything below concerns
later vintages, and none of it can change a frozen value: the assembly gates refuse
to build a vintage in which any published 2010–2023 cell would differ.

## The frozen index (2010–2023)

The object behind the published estimates. Nine applications, 140 benchmarks, as
documented in the paper's Online Appendix Section C. Released as v1.0.0 together
with the 2024 refresh. An errata file (`data/derived/errata_frozen_workbook_v1.csv`)
lists four small transcription discrepancies found when checking the source workbook
against the original repositories; the released frozen data are kept exactly as the
paper estimated them, and the corrections apply from the 2024 chain point, where two
of them (which would otherwise create or move state-of-the-art frontiers) can take
effect without touching anything the paper reports.

## The 2024 refresh

Appends 2024 to the frozen window from the recovered Papers with Code archive,
basket-faithfully: 143 benchmarks over the same nine applications (three archive
continuations enter in image comprehension). No new applications, no membership
changes.

## The 2025 vintage

Covers 2010–2025 with a single chain point at the 2023–2024 seam. What it adds:

**Eight admitted benchmark series**, each with a declared source, scale, evaluation
protocol and licence, and — where the series is used in any human-comparison
reading — a documented human reference value with quoted evidence. Series that only
feed progress may enter without a reference value, which is the frozen basket's own
standard (65 of its 149 benchmark series carried none).

| Series | Application | Reference | Notes |
|---|---|---|---|
| METR task horizons (80% reliability) | Agentic task execution | 960 min, instrument ceiling | The primary agentic series: the length of real computer-based work task, in minutes of human working time, completed at 80% reliability. Pinned to METR-Horizon v1.1; used with METR's written permission (cite METR; METR is not affiliated with this work). The suite's 50%-reliability variant was retired when frontier systems outgrew its 16-hour range; the two variants are one construct and are never in the basket together. |
| OSWorld | Agentic task execution | 72.36, human | Real desktop computer work; externally collected scores, mixed agent scaffolds, declared as such. |
| GDPval | Agentic task execution | 50, parity by construction | Scored as a win rate against human professionals, so 50 is parity by definition. |
| TheAgentCompany | Agentic task execution | 95, ceiling (discounted) | Corroboration series, not in the basket: pinned to one simulation environment (results from other environments excluded so an environment change is never booked as capability); the ceiling is discounted by the same convention as SWE-bench. |
| GPQA Diamond | Mathematical and scientific reasoning | 81.3, expert | Graduate-level science questions, "Google-proof" by design. |
| MATH Level 5 | Mathematical and scientific reasoning | 90, expert (full-set figure, declared caveat) | Competition mathematics; near-saturated, so it adds precision and corroboration rather than increment. |
| SWE-bench Verified | Software engineering | 95, ceiling (discounted) | Real GitHub issue resolution, human-screened task subset; Epoch-run harness. |
| ToMBench | Conversation | 86.1, human | Theory of mind through everyday social scenarios. |
| SimpleBench | Language comprehension and QA | 83.7, human (n=9, declared caveat) | Adversarial everyday reasoning; organisers' own runs on a private test set. |

(Nine rows because TheAgentCompany is carried as corroboration outside the basket.)

**Two new application areas with exposure columns.** Agentic task execution and
mathematical and scientific reasoning enter with their own occupation exposure
columns. Their ability-relevance rows come from the same expert matrix as every
other application: Felten, Raj and Seamans (2018) scored sixteen application areas,
and the two technical-problem rows serve the two new areas. The borrowed rows were
validated by an independent LLM re-scoring that reproduces the expert matrix at
r ≈ 0.78 held-out (the two rows themselves at 0.80 and 0.79), confirmed by a second,
independently prompted model from a different vendor (0.81 and 0.80 against the same
expert rows). Conversation and software engineering use their original expert rows.
Both new columns are chained: no values before 2024.

**Composite membership.** The generative-AI composite keeps its name and broadens
its membership at the chain point, adding conversation and software engineering to
language modelling and image generation; the frozen generative-AI column is
unaffected and the narrow-membership continuation is recorded alongside. Agentic
task execution and mathematical and scientific reasoning are not members of either
original composite.

**A second-generation overall composite** (`daioe_g2all`) is published as an
additional column. As new capability domains with different native scales enter the
basket, a companion aggregate is useful in which every application's annual progress
is expressed in units of its own historical year-to-year variation and averaged over
the applications observed that year — one uniform rule for old and new areas alike,
robust to each benchmark family's scale conventions. It carries a complete 2010–2025
history of its own (before 2024 it simply runs over the nine original areas) and is
validated on three declared checks: invariance to an alternative axis convention for
the METR series (13.7% shift, bound 15%), no single application above half of any
chained year's standardised composite (maximum 35%), and within-year rank agreement
with the original composite (0.99 in 2023 and 2025). The original all-applications
composite continues unchanged; the σ-table behind the standardisation is released
as `data/derived/g2_sigma_v1.csv`.

**Known caveats, shipped rather than filed.** A newly admitted series' first
increment is computed against its entry-year frontier; where that baseline is thin
(SWE-bench Verified: one 2024 evaluation; ToMBench: two), the 2025 increment is an
upper bound, revisable as harnesses evaluate earlier models retrospectively. Five of
the nine original applications have no living 2025 source (the archive died; the
capabilities did not stop), so their series are carried at their last level. Vintage
values beyond 2023 are revisable in later vintages; the frozen window is not.

## Provenance and verification

Every admitted series has a provenance sidecar (`data/updates/provenance_*.json`)
with content hashes. Every human reference value is in
`data/derived/human_anchors_v1.csv` with its source and a quoted passage. Every
vintage assembly re-verifies, cell by cell, that all frozen published values are
unchanged in every occupational taxonomy before anything is written, and that no
admitted series carries a value before its chain year.
