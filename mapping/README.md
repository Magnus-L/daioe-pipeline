# The mapping-matrix pipeline: adding subdomains semi-automatically

Copied into the workspace 7 August 2026 from the read-only legacy archive at
`-JOBB/EK_ANALYS/AI/STUDY_Y_Unboxed_AI/Social-skills-ai-solution/`. Nothing in the original was
modified. This is the machinery behind Online Appendix J: it scores each AI application against
each of the 58 abilities (52 O*NET abilities plus the six social skills) with an LLM under
anchored, retrieval-augmented prompting, and produces the 9x58 matrix.

## Why it matters now

Magnus's instruction of 7 August: a measure that omits agentic AI in 2026 is not describing the
world, so the 2024-2026 vintage must add subdomains, not only metrics. The extension door built
today admits the *series*; a new subdomain additionally needs a **row in the mapping matrix**, and
this is the tool that produces one. It is the difference between refilling the existing nine
applications and actually extending what the measure covers.

## What is here, and what it does

| | |
|---|---|
| `code/estimate_mapping.py` | the scorer: 9x58 pairs, two models, mean of the two |
| `code/validate_against_frs.py` | replication check against the FRS 2018 matrix |
| `code/compute_occupation_exposure.py` | builds DAIOE from the matrix without the social discount |
| `raw_data/applications.csv` | the applications to score. **Extended today, see below** |
| `raw_data/abilities.csv` | the 58 abilities and their O*NET definitions |
| `raw_data/anchors.csv` | per-application high/low calibration examples derived from FRS |
| `output/mapping_matrix_9x58_v2018.csv` | the published matrix |

**The appendix's numbers are traceable to this pipeline and reproduce here.**
`output/FRS_validation_report.json` gives `pearson_corr_flat = 0.7762` and `mae_flat = 0.1258`
against FRS across nine aligned rows, which is exactly what Online Appendix J reports. Note that
the *other* file, `validation_report_v2018.json`, says `"status": "no_overlap_detected"` and is
stale; do not quote it.

`run_report_v2018.json` records the run: 522 pairs, 9 applications, 58 abilities, primary model
`gpt-4o` and secondary `gpt-4o-mini`, scores averaged across the two.

## What I changed

Three applications appended to `raw_data/applications.csv`, chosen because they are the
subdomains Track B's evidence review found had live, dated, licence-clean anchors
(`notes/track-b-b3-subdomain-evidence.md`):

    10  Agentic task execution
    11  Mathematical and scientific reasoning
    12  Software engineering

Their definitions are drafted in `raw_data/applications_definitions_new.csv`, written to match
the register of the existing nine and to be explicit about the measured object. The agentic
definition says plainly that the object is the model *with* its scaffolding, because that is what
a firm deploys and because the protocol-purity doctrine requires the object to be declared.

## Three things that must be settled before this is run, and none is optional

**1. New applications currently have no anchors, and the prompt is different without them.**
`estimate_mapping.py` groups anchors by application (`anchors_by_app.get(app_id)`), so
applications 10 to 12 would be scored with empty high/low examples while the original nine were
scored with up to five of each. That is not the same instrument. The FRS-derived anchors cannot
be extended mechanically, because a new application has no FRS row to derive them from, so
someone has to write a handful of high and low examples per new application. That is a small,
bounded research judgement and it belongs to Magnus and Erik, not to the tool.

**2. The whole matrix must be re-scored in one run, not appended to.**
The existing rows were scored by `gpt-4o` and `gpt-4o-mini` in October 2018-vantage prompting.
Appending rows scored by any other model, or at any other vantage, recreates precisely the
defect that argued for adopting this matrix in the first place: a hybrid in which the relative
weight of an old subdomain against a new one depends on which instrument scored it. Re-score all
twelve together.

**3. It needs an OpenAI API key, and that is Magnus's call.**
`call_llm` uses the OpenAI SDK directly. Roughly 12 applications x 58 abilities x 2 models is
about 1,400 short calls. The content sent is public O*NET ability definitions and our own
application definitions, with no register or personal data, so it sits in the green zone, but it
is an egress decision and the key is not mine to supply.

## What follows once the matrix exists

A new subdomain also needs an entry in `_APP_NAME` and `_APP_ID` in `stage2_ai_progress.py`, and
an id that does not clash with the existing set (2, 5-12, 18). Note the two numbering systems are
independent: this pipeline numbers applications 1-12 in its own space, DAIOE numbers them
differently. Do not assume they align.

Then the series themselves enter through the extension door
(`notes/EXTENSION-door_2026-08-07.md`), chained at 2024, with a sourced anchor each.
