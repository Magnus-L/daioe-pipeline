# Validation status — DAIOE Python port vs Stata

**v1 (full reproduction of the 2010–2023 panel) is complete.** The Python pipeline
reproduces Erik Engberg's Stata DAIOE construction **bit-for-bit (max|diff| = 0.0)** on
every substantive value, across all five occupational classifications and all five
publication panels. Run `python run_all.py` to regenerate the two reports under `reports/`.

## What is validated bit-exact (0.0)
- **Stages 1–4** — 11/11 intermediate + panel targets at 0.0: O*NET r_oj (`element_impact`),
  social skills S_o, AI progress Δp_it (`slopes`), the Felten mapping matrix, and the full
  O*NET-level index (`exp_change_*`/`exp_cumul_*` for all 13 application categories).
- **Stage 5** — all five internal panels (onet/soc/isco08/ssyk2012/ssyk96) and all five
  publication panels (`daioe_{onetsoc2010,soc2010,isco08,ssyk2012,ssyk96}.{dta,csv,xlsx}`):
  every `daioe_*`/`exp_change_*`/`exp_cumul_*` value, all five comparator indices (FRS18,
  FRS21/AIOE, Webb, Frey-Osborne, OpenAI-2024), the occupation-characteristic columns, the
  SSYK digit levels, and all NaN masks.
- **Percentile ranks** — all 60 `pctl_rank_*` columns pass the **tie-aware** check
  (`compare_pctl_tie_aware`): every non-tied rank matches exactly, and within every
  tied-value block the multiset of assigned ranks matches the reference.

## The float32 lesson (why this took care)
The Stata pipeline **evaluates expressions in double then stores each `gen`/`egen`/`replace`
in the variable's type — `float` (single precision) by default.** A naive float64 port
drifts ~1e-7 per step; the index's `social_score² × 10 × 12-year cumulate` amplifies that
past any sane tolerance on the composite columns. The fix is to mirror Stata's storage at
**each** step (`stata_ops.f32`, keyed off `stata_storage_types`): compute in double, cast to
float32 where Stata stored a float. The decisive subtlety was the social-skill rescale —
`collapse(sum)` stores the sum as **double** but `egen max` stores the max as **float**, so
the division is `double / float32(max)`, which is why the reference leader sits at
`0.99999998`, not `1.0`.

## Two irreducible residuals (inherent Stata non-determinism, not value errors)
1. **Percentile-rank within-tie order.** Stata's `pctl_rank` does `sort year <value>`, and
   Stata's default sort is an **unstable quicksort**. Rows whose ranked value is exactly tied
   (e.g. the 772 occupations all at `daioe=0` for an application with no early exposure) get a
   block of consecutive ranks in a non-reproducible order. The ranked values are identical
   (0.0); only the within-tie permutation differs. The tie-aware validation proves equivalence
   up to this permutation. The reference itself is non-deterministic here.
2. **11 `conseq_error` cells** (`daioe_panel_soc` 8, `isco08`/`ssyk2012`/`ssyk96` 1 each) land
   on exact-half rounding boundaries (x.xx5) where `round(·, 0.01)` flips on a 1-ULP difference
   in the collapse-mean's summation order. `conseq_error` is a double-stored occupation
   characteristic **dropped from every publication panel**, so no deliverable is affected.

Neither residual touches any DAIOE value or any shipped panel.

## Reproduce
```bash
python run_all.py            # stages 1-5 -> reports/validation_<ts>.md + validation_pctl_<ts>.md
pytest -q                    # Stata-idiom shim unit tests
```
The strict report shows 17/21 value targets PASS; the 4 "FAIL" are exclusively the 11
`conseq_error` cells above. The tie-aware report shows 60/60 pctl columns PASS.

## Refresh mode (Phase 2 addendum, 2026-07-07)
With `benchmark_updates` active the frozen-target validation intentionally fails
(the update revises 2016–2023); the refresh gates are instead: (1) `pytest -q`
green, (2) empty-update run still bit-exact, (3) `scripts/refresh_report.py`
shows zero ref-only rows (nothing lost), no negative progress means, no
cumulative decreases, and a seam quantification consistent with
`notes/track-a-seam-audit.md` (independently derived, full agreement 2026-07-07).
Seam policy DECIDED 2026-07-07 (Magnus; Erik notified): **freeze history** — the
published 2010–2023 series is immutable; only year >2023 values are appended, with
a documented vintage-splice at 2023. The Atari-backfill revision evidence is retained
(`notes/track-a-seam-audit.md`) and is expected to be adopted in one step at the
Economic Journal R&R, when the full series is re-run from the port.
See `notes/checkpoint2-seam-policy.md`.
