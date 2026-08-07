# AI‑Unboxed: FRS‑style Mapping & DAIOE Robustness Pipeline

This project builds and validates an **AI application → ability/skill** mapping (FRS 2018 style) and then computes occupation‑level AI exposure (DAIOE) for robustness checks against our original index.

The pipeline is **pure Python** and runs end‑to‑end via a single master script. No bash is required.

## Contents (high‑level)
1. **Standardize applications** (FRS terminology).
2. **Anchors (high/low) per ability** from FRS “Combined” (max/min per ability).  
3. **Estimate mapping 9×58** (applications × abilities/skills) with LLM prompts.
4. **Validate** against FRS (2018) “Combined” matrix.
5. Build **occupation×ability weights** from O*NET (Importance × Level).
6. Compute **ΔDAIOE (Eq. 3, robustness variant)** from annual progress Δp (Eq. 2) for a target year using `raw_data/delta_progress.csv`.
7. Compute **level DAIOE (Eq. 6)** by **summing yearly ΔDAIOE**; no cumulative-progress input is needed.

## Key inputs
Place these in the project root or `raw_data/` as noted:

- `raw_data/applications.csv`  
  Columns: `ai_app_id,name`. Names must match FRS terms (the master script auto‑harmonizes common aliases):  
  `Visual question answering`, `Generating images`, `Language modeling`, `Image recognition`,  
  `Reading comprehension`, `Translation`, `Speech recognition`, `Abstract strategy games`, `Real-time video games`.

- `raw_data/abilities.csv`  
  58 rows (52 O*NET Abilities + 6 social skills), with `ability_id, ability_name, ability_definition`.

- `mapping_matrix.xlsx`  
  Must contain sheet **`Combined`** with FRS (2018) application rows and ability columns.

- `Abilities.xlsx` and `Skills.xlsx`  
  O*NET tables used to build occupation×ability weights (Importance & Level).

- **Annual progress (Δp)**: `raw_data/delta_progress.csv` (**long format**)  
  Columns: `ai_app_id` (or `name`), `year`, `delta_p`.  
  Missing app‑years are treated as 0 that year.

## Core outputs (written to `output/`)
- `mapping_matrix_9x58_v2018.csv` — estimated 9×58 matrix.
- `comparison_our_vs_frs_v2018.csv` — validation results vs FRS “Combined”.
- `final_exposure_comparison.csv` — exposures A/B and join with original DAIOE.
- `new_daioe_<YEAR>.csv` — **ΔDAIOE** for `<YEAR>` (Eq. 3 robustness variant).
- `new_daioe_cumulative_<YEAR>.csv` — **level DAIOE** up to `<YEAR>` (Eq. 6 = sum of yearly ΔDAIOE).
- `new_daioe_timeseries.csv` — panel with Δe, ΔDAIOE, and cumulative DAIOE by year.
- `final_exposure_comparison_with_new_and_cumulative_daioe.csv` — merged comparison table.
- `summary.json`, `summary_tables.csv` — quick stats (correlations, top/bottom lists, rank changes).

## How to run (Python only)
Create a tiny **runner** in the **project root** (same level as `code/`) named `run_pipeline.py`:

```python
# run_pipeline.py
import os, sys, runpy
from pathlib import Path

# (optional) model names for estimate_mapping.py
os.environ["MODEL_PRIMARY"] = "gpt-4o"
os.environ["MODEL_SECONDARY"] = "gpt-4o-mini"

# Choose Eq.(3) target year; if omitted, the master script picks the max year available
sys.argv = ["master_pipeline.py", "--year", "2023"]

ROOT = Path(__file__).resolve().parent
runpy.run_path(str(ROOT / "code" / "master_pipeline.py"), run_name="__main__")
```

Run it from Python (IDE or REPL):
```python
import runpy; runpy.run_path("run_pipeline.py", run_name="__main__")
```

## Method in brief

### Terminology harmonization
We standardize common aliases to FRS terms (e.g., *Image comprehension → Visual question answering*, *Image generation → Generating images*, *Language modelling → Language modeling*, *Real‑time → Real-time*). This ensures one‑to‑one alignment to the nine FRS applications.

### Anchors (high/low)
From the FRS `Combined` sheet, for each of the **52 O*NET Abilities** we pick the **max** and **min** application as LLM “anchors.” For the **6 social skills**, we apply a conservative heuristic (language/speech apps as high anchors; visual/control apps as low anchors). The master script writes `raw_data/anchors.csv` automatically.

### Mapping and validation
We estimate a 9×58 mapping with LLM prompts and **validate** it against FRS (2018) “Combined” numbers, reporting correlations and fit diagnostics.

### Occupation weights
From O*NET `Abilities.xlsx` and `Skills.xlsx` we compute **occ×ability weights** as normalized `Importance × Level` for the 58 abilities/skills.

### ΔDAIOE (Eq. 3, robustness variant) and Level DAIOE (Eq. 6)
We form the exposure kernel per occupation and application as
\[
E_{oi} \;=\; \sum_{j=1}^{52} r_{o,j}\,x_{i,j}, \quad
r_{o,j} \;=\; rac{i_{o,j} l_{o,j}}{\sum_{j=1}^{52} i_{o,j} l_{o,j}}.
\]
Using **annual** progress Δp (Eq. 2),
\[
\Delta e_{o,t} = \sum_i \Delta p_{i,t} E_{oi},\qquad
\Delta \mathrm{DAIOE}_{o,t} = (\Delta e_{o,t})^2
\]
(no social discount in the robustness variant). The **level** index is
\[
\mathrm{DAIOE}_{o,t} = \sum_{	au \le t} \Delta \mathrm{DAIOE}_{o,	au}\,.
\]

### Notes on robustness goal
We recompute exposure using FRS‑style mapping and annual Δp without any social‑skill discounting, then compare occupation rankings against our original DAIOE to assess robustness.

## Troubleshooting & sanity checks
- Ensure `mapping_matrix.xlsx` has the **`Combined`** sheet.
- Verify `raw_data/applications.csv` contains exactly the nine FRS apps (names will be normalized).
- Check that `raw_data/delta_progress.csv` covers the year(s) you wish to analyze.
