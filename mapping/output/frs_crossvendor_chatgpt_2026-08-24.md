# Cross-vendor concordance check of the two borrowed FRS 2018 rows — 24 Aug 2026

A second, independently prompted model from a different vendor (ChatGPT, reasoning
mode) scored the two candidate applications (agentic task execution; mathematical
and scientific reasoning) against the 52 O*NET abilities from definitions alone.
Raw scores: `frs_crossvendor_chatgpt_2026-08-24.csv` (this folder).

Results against the shipped FRS 2018 basis: Pearson 0.806 (agentic), 0.801
(maths). Agreement with the first model's re-scoring (Claude): 0.917 / 0.906 —
the two models agree with each other more than either agrees with the 2018 expert
rows, and their deviations from 2018 are vendor-concordant (documented evidence
for a possible declared row revision at a future chain point, not noise). No cell
shows the two models deviating from FRS 2018 in opposite directions.

Caveat, stated rather than hidden: both models were plausibly trained on the
published 2018 matrix, so "from definitions alone" limits the prompt, not the
models' prior exposure; the exercise is a consistency check, not a validation of
the rows as occupational-ability mappings for the new constructs. Blinded human
expert re-rating remains declared future work at a chain point.
