# VERIFICATION.md — code-verification ledger, daioe-pipeline (the measure)

Ledger under the AI-Econ Lab code-verification protocol (pilot: proworker-gov,
26 Jul 2026). Full findings detail: `../daioe/notes/code-review-2026-08-08.md`.

- **Repo state verified:** `394acfa` (clean tree) plus the same-day fixes committed after
  this review. **Verification date:** 2026-08-08 (evening).
- **Execution:** local public-data code; the test suite and the exhibit scripts were
  executed read-only; nothing register-side.
- **Method:** two adversarial lens agents (construction-vs-paper; crosswalks and paper
  exhibits) plus the style pass; same-day repairs by Claude; **ML adjudication pending.**

## Entries

### 2026-08-08 — construction-vs-paper lens (Eqs 1–6, freeze, vintage)
- **Result, clean:** every equation of Section 2.1 verified in `src` (r_oj, Δe_jt, Δe_ot,
  S_o, weight-before-square, cumulation from 2010; non-negativity structural); the
  published-window bit-exactness gate is real twice over (validation vs Erik's .dta
  17/21 strict + 60/60 tie-aware, the strict misses being the 11 documented
  conseq-error boundary cells; assembly gates G1/G2/G2b exact on every published cell);
  entrant composition-neutrality and the genai seam behave exactly as the OA doctrine
  states; Track A guards and the Epoch adapter tested and correct.
- **Tests run:** `pytest tests/ -q` → **43 passed** (94s). `preflight.py` exits 1 on five
  false alarms (its own name templates; the data/derived fallback it does not know).
- **Findings:** PL-H1 the OA/DOCUMENTATION "frozen 2010–2020 standardisation moments,
  mean zero sd one in every vintage" invariant is implemented nowhere and is false of the
  released raw panels — the real moments live in the estimation build (B20, gated); OA
  and DOCUMENTATION.md restated to the enforced invariant (cell bit-identity) same day.
  PL-M1 the ×10 scale factor in stage4 is absent from the paper's equations (now
  disclosed in the no-natural-units footnote). PL-M2 assembly gates G2/G2b silently skip
  columns missing from the vintage build (needs a column-completeness assert). PL-M3
  `apply_conseq_error`/`conseq_error_weight` are dead config switches. PL-M4 the
  jump-spread handles gaps of 2–5 years only; glapp ≥ 6 would zero silently in future
  refreshes. PL-M5 no tests cover Eq 5/6 composition, stage1/stage2 internals, stage5
  helpers, or the seven extension guards. PL-L: roe double-spike in vintage internals;
  preflight name templates; freeze boundary a code-side default; documentation-authority
  contradiction (README vs DOCUMENTATION); stale README claims (12→43 tests; validation
  status); OA threshold-column "corrected in the released pipeline" overstated (fixed);
  dead `_NINE_PARENTS`; duplicated scale lists; `_load_extensions` runs twice per build.

### 2026-08-08 — crosswalk and exhibit lens (t01/t02, variants, basket, Webb, SOC2018)
- **Result, clean:** E1 (0.51/0.58, n=743, p-values), the T02 battery (1.00; 0.855;
  99.9/99.1; arrival profile; subdomain paths −0.69/0.11/0.75; chronology; ads t=1.5),
  every cell of both transparency tables, all basket counts (140/149, peaks, 2023,
  videogames 57→10), the Webb reconciliation (8 occupations, ratio exactly 4, enriched
  score wins), the SOC2018 round-trip (exact), and all three OA figures (byte-identical
  to the pipeline reports) verified against code and data.
- **Findings:** **PL-H2 (CV-H7) the E2 industry gradient silently dropped the combined
  register group M+N in every country** (`SNI_TO_NACE` keyed "M"/"N" against a register
  that carries "M+N"): fixed (M and N adoption pooled, unweighted mean; same fix in
  exhibit 3), re-run — SE 0.883 (n=9, p=0.0016), DK 0.964 (n=7, p=0.0005), PT 0.867
  (n=9, p=0.0025), replacing 0.88/0.94/0.81 on 8/6/8; figures regenerated and copied to
  the paper; paper and matrix corrected with provenance. PL-M6 OA D1's opening
  misdescribed the basket rule (span membership, not frontier movement) — fixed. PL-M7
  videogames 5.53/0.553 double-rounding (true 5.5248/0.55248) — fixed to 5.52/0.552.
  PL-M8 rank-one shares mixed centred and uncentred bases (99.9/99.1 uncentred vs 41
  centred) — bases now stated (96.8 centred composite changes; 65 uncentred family).
  PL-M9 variant-table caption N 438 → effective 424 — fixed. PL-M10 acquisition
  channels are multi-select; "a further" additive phrasing — fixed. PL-L: 430→429
  matched occupations (fixed); mapping-matrix "9×52 file" wording (fixed: one 16×52
  file); hard-coded "Figure B3" (currently correct); AEI outcome is a conversation
  share, not per-worker (noted); stale CERTIFICATION.txt describes the superseded
  algebraic variant build; the transparency source-note points at the daioe notes dir.

### AI provenance (Rule V8)
The pipeline was built and validated with AI assistance across the Aug 2026 sessions
under ML's specifications (see VALIDATION.md); this review was performed by Claude lens
agents on 2026-08-08 with same-day repairs (M+N fix + re-run; DOCUMENTATION restatement)
committed to this repo. The M+N correction changes two published exhibit values and is
flagged in red in the paper pending co-author review.

## Open items (Erik / next round)

G2 column-completeness assert; delete or implement the conseq-error switches; glapp ≥ 6
guard; tests for Eq 5/6, the seven extension guards, and the splice; preflight name
templates; README refresh (43 tests; validation status; stata_code symlink); roe spike
zeroing; single authority statement for code-vs-appendix divergences (with the ×10 and
conseq-error rows enumerated).

From the 25 Aug 2026 described-vs-implemented audit (notes/AUDIT-…_2026-08-25.md):
- ~~Fold the frozen-pctl restore into the wiring~~ DONE same day: the wiring script
  now runs `restore_frozen_pctl_20260825.py` itself, whose closing byte-identity
  assert against dist doubles as the gate. Nothing manual remains; no action needed.
- ~~dist refresh-2024 stale~~ RESOLVED 25 Aug (Magnus: rebuild): the July snapshot had
  recomputed the published window because the Track A workbook's recovered 2016–2023
  rows ran through the plain pipeline. Rebuilt under the seam discipline
  (`scripts/rebuild_refresh2024_seam_20260825.py`): frozen window verbatim (G1 + both
  seam gates 0 diffs; ranks pinned to the canonical published files, byte-identity
  assert), 2024 chained at the seam (966/772/438/429/354 rows across the five
  taxonomies; 143 series; 10 with a positive 2024 frontier move). Bundle repointed and
  re-staged, 36 files checksummed, frozen-vs-refresh shared window 0 diffs. The old
  snapshot (`data/out_refresh2024_snapshot/`) is kept for provenance, never ships.
  2024 levels vs the stale build: rank correlation 0.99, mean level 33.2 vs 31.4.
  **v1.0.0 is publishable again.**
- From the 25 Aug cross-vendor pass (notes/CROSSVENDOR-VERDICT-release-docs_2026-08-25.md):
  (i) NO code consumes errata_frozen_workbook_v1.csv — chain-point application of the four
  errata is declared policy with no implementing mechanism; build it into the next vintage
  assembly or keep deferring explicitly. (ii) Consider tie-invariant midrank pctl columns
  as NEW columns in v1.1.0 (legacy ranks stay frozen). (iii) Machine-readable
  DATA_DICTIONARY per bundle. (iv) .tsv naming decision before first publication.
