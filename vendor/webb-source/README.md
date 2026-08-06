# Webb (2020) source data — off-machine backup copy

**Canonical home:** `lab-infrastructure/ai-exposure-measures/raw/webb/original/`, which
carries the full README, the provenance, and `scripts/build_webb_from_source.py`.

This copy exists because that directory is not a git repo, and these files are hard to
replace: they are not on Webb's site, not on GitHub, not in Wayback, and not in the paper.
They live on a Notion page behind a Mailchimp email gate. Getting them again means going
back through the gate.

This repo is **private**, and must stay private for these files: Webb gates the data so he
can notify users of updates and report usage to funders. A public copy would circumvent that.

## Why the pipeline keeps them at all

`data/derived/webb_indices_soc2010_reconciled.dta` corrects eight `robot_score` values that
the 27 May delivery's `1_data_ore` copy inflates exactly fourfold. `webb_final_df_out_onetsoc.dta`
is Webb's own O*NET-SOC file and is the evidence for that correction: collapsed to SOC2010 by
unweighted mean, it matches the enriched vintage to 5.96e-08 and the raw one to 1.436.

Full working in `notes/validation-gate-restored-2026-08-06.md`.

## Files

| file | unit | rows | stamped |
|---|---|---|---|
| `webb_final_df_out_onetsoc.dta` | O*NET-SOC 8-digit | 964 | 2018-04-23 |
| `webb_onet_to_occ1990dd.dta` | O*NET-SOC | 963 | 2019-02-04 |
| `webb_exposure_by_occ1990dd_lswt2010.dta` | occ1990dd | 341 | 2019-07-13 |

`.csv` renditions alongside; the `.dta` files are authoritative. Never move the `.dta` files
through a clipboard: they are binary, and pasting them as text silently destroys every number.
