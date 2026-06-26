# daioe-pipeline

A faithful Python port of Erik Engberg's Stata construction of the **Dynamic AI
Occupational Exposure (DAIOE)** index, with byte-near-exact validation against the
frozen Stata outputs and a config-driven path to (a) annual updates through the most
recent full year and (b) additional occupational classifications.

Serves both the *AI Unboxed* (EJ) and *DAIOE-extensions* papers. See the design plan at
`~/.claude/plans/magical-napping-ocean.md` and the spec memo at
`../daioe-extensions/notes/auto-update-pipeline-spec.md`.

## Why
The only time-varying input to DAIOE is the AI benchmark-progress vector (Δp_it). The
O*NET relevance matrix r_oj, the Felten mapping matrix x_ij, the social-skill discount
and δ=2 are fixed. So the engine is deterministic matrix algebra, and Erik's existing
output `.dta` files are an exact ground truth. Benchmark collection is manual (EFF +
Papers With Code; no Hugging Face), so an annual refresh = append benchmark rows + bump
`year_final`.

## Layout
```
config.yaml            run parameters (mirrors 0_2_settings.do)
run_all.py             entry point: stages 1-5 + validation report
src/daioe/
  config.py io.py stata_ops.py validate.py
  stage1_onet.py  stage2_ai_progress.py  stage3_mapping.py
  stage4_index.py stage5_taxonomies.py
tests/                 unit tests for the Stata-idiom shims
data/  raw,enriched_ref,reference -> read-only symlinks into the Stata source
       out/            our outputs
reports/               validation_<ts>.md
```

## The five stages (run order; each validated against a Stata `.dta`)
1. **stage1_onet** — r_oj (`element_impact`) + S_o (social skills) from O*NET 22.2.
2. **stage2_ai_progress** — Δp_it from benchmark SOTA frontiers (the time-varying input).
3. **stage3_mapping** — Felten x_ij mapping matrix.
4. **stage4_index** — Δe_jt → Δe_ot → social×square×10 → cumulate → percentile rank.
5. **stage5_taxonomies** — translate SOC2010 → ISCO08/SSYK2012/SSYK96 (+ SOC2018/SSYK2025),
   merge comparator indices, write internal + publication panels.

Stages 1–3 are independent; 4 needs 1–3; 5 needs 4.

## Run
```bash
python run_all.py                  # all stages + validation report
python run_all.py --stages 1,2,3   # subset
pytest -q                          # shim unit tests
```

## Annual update (Phase 2)
Append the new year's benchmark rows to `measures_metrics_newdata2023.xlsx`, bump
`year_final` in `config.yaml`, rerun. The 2010–2023 slice must still match the frozen
targets; ≥2024 is checked for internal consistency.

## Add a taxonomy (Phase 3)
Add an entry to `taxonomies` in `config.yaml` (crosswalk path, key, level rule) and drop
the crosswalk into the data folder. SOC2018 crosswalk is available; SSYK2025 is blocked
on an SCB crosswalk.

## Validation bar
A column passes if max|got−ref| ≤ 1e-6 (internal/double) and matches float32 publication
storage (1e-5); any worse column is flagged in the report rather than silently passed.
**The Stata code is authoritative over the paper appendix** wherever they differ.
