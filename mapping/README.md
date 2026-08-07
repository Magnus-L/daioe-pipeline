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

## The v2 pipeline (7 Aug 2026): what replaced the three blockers

Full reasoning in `notes/MAPPING-claude-port-and-frs16_2026-08-07.md`. In short:

**Blocker 1 (new applications have no anchors) is mostly gone.** FRS 2018 scored **sixteen**
applications, not nine, and three of the seven DAIOE never used are the subdomains we are adding:
agentic execution, maths and science reasoning, and software engineering. Their anchors are derived
from FRS by the same procedure as everyone else's. Only the agentic mapping is a judgement rather
than a lookup, and the evidence for it is set out in the note.

**Blocker 2 (re-score everything in one run) stands, and is now enforced.** `applications_v2.csv`
carries all twelve, and `estimate_mapping_claude.py` scores them together or not at all.

**Blocker 3 is now an Anthropic key, not an OpenAI one.** Same green-zone payload, same egress
decision. `ANTHROPIC_API_KEY` or `ant auth login`.

Two further defects turned up while porting and are fixed here: the published run passed **no
application definitions at all** (`app.get("short_definition", "")` against a file with no such
column), and anchor coverage ranged from 17 high / 17 low to 1 high / 0 low across the nine, so the
applications were never scored by the same instrument.

## v2 files

| | |
|---|---|
| `raw_data/applications_v2.csv` | twelve applications, each with a definition and its declared FRS row |
| `code/build_anchors_v2.py` | balanced anchors, each application's own top-8 / bottom-8 from its FRS row |
| `raw_data/anchors_v2.csv` | the anchors themselves |
| `mod_data/anchor_cells_v2.csv` | the held-out set: cells whose FRS value the prompt reveals |
| `code/estimate_mapping_claude.py` | the scorer: Opus 5, structured outputs, batch, caching, replicates |
| `code/validate_mapping_v2.py` | agreement with FRS, reported both all-cells and held-out |

## What the published validation figure is worth

`validate_mapping_v2.py` reproduces Online Appendix J exactly (Pearson 0.7762, MAE 0.1258, n=468),
which is how we know the alignment is right. Excluding the 52 cells whose FRS value appeared in the
prompt that produced them, it is **0.6887**. The appendix is not wrong about what it computed, but
0.689 is the bar a new run must clear, not 0.776.

## Run order

    python code/build_anchors_v2.py
    python code/estimate_mapping_claude.py --dry-run                      # requests + cost, no API
    for e in low medium high xhigh; do                                    # ~$0.44 each
      python code/estimate_mapping_claude.py --sync --sample 5 --replicates 1 --effort $e --tag sweep_$e
      python code/validate_mapping_v2.py --matrix output/mapping_matrix_claude_vsweep_$e.csv --label sweep_$e
    done
    python code/estimate_mapping_claude.py --submit --effort <winner>     # full run, ~$11-15
    python code/estimate_mapping_claude.py --collect <BATCH_ID>
    python code/validate_mapping_v2.py --matrix output/mapping_matrix_claude_v2026.csv

## What follows once the matrix exists

A new subdomain also needs an entry in `_APP_NAME` and `_APP_ID` in `stage2_ai_progress.py`, and
an id that does not clash with the existing set (2, 5-12, 18). Note the two numbering systems are
independent: this pipeline numbers applications 1-12 in its own space, DAIOE numbers them
differently. Do not assume they align.

Then the series themselves enter through the extension door
(`notes/EXTENSION-door_2026-08-07.md`), chained at 2024, with a sourced anchor each.
