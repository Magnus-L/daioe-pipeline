"""Stage 4 — DAIOE index construction (the core).

This stage turns three fixed ingredients into the occupation-year DAIOE panel:

  1. yearly AI *progress* per application  (slopes_slimmed_<app>, Stage 2),
  2. the application->ability *relevance* matrix  (mapping matrix, Stage 3),
  3. O*NET occupation *ability profiles* + social/consequence characteristics
     (Stage 1).

The economic logic, following Felten/Raj/Seamans and our DAIOE extension, is a
two-step pass-through. AI progress in an application during a year first raises
the exposure of every *ability* that application is relevant for (Eq2). Each
occupation then inherits a change in exposure equal to its ability profile dotted
with those ability-level exposure changes (Eq3). Finally the occupation-level
change is discounted for social-skill intensity, squared to spread the
distribution, and scaled up; the cumulative sum over years is the index level
(Eq6). The whole pass is repeated for each application category to build the
sub-indices.

AUTHORITATIVE SOURCE: Code/1_2_merge_and_construct_index.do. Where this code and
the appendix equations disagree, the do-file wins (see ``CODE_VS_APPENDIX`` and
the comments at the social-discount step).

We read every input from the Stage 1-3 parquet checkpoints in ``cfg.out_file``
and write ``daioe_panel_onet_preliminary.parquet`` for Stage 5.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import io, stata_ops as so
from . import validate as validate_mod


def _f32(x):
    """Round to Stata `float` (single precision) storage.

    The do-file never declares `double`, so every ``gen``/``egen``/``replace``
    stores its result as a 32-bit float. Stata evaluates an expression in double
    precision and then *stores* the result at the variable's type, so we mirror
    this by computing in float64 and casting the STORED result to float32 (then
    back to float64 for downstream arithmetic). Omitting this leaves diffs of
    order 1e-6..1e-5 that grow with the number of applications summed and with the
    cumulative sum — exactly the failure signature before this was applied.
    """
    if isinstance(x, pd.Series):
        return x.astype(np.float32).astype(np.float64)
    return np.float64(np.float32(x))

# Documented divergence between the authoritative Stata code and the appendix.
# The appendix Eq5 applies the social discount differently; the code computes
# final exp_change = (Delta e_ot * social_score)**2 * scale_up, with the
# consequence-of-error discount DISABLED. We reproduce the code, not Eq5.
CODE_VS_APPENDIX = (
    "Social discount applied as (Delta e_ot * social_score)**2 * scale_up "
    "(do-file lines 169-208); consequence-of-error discount is computed but "
    "NOT applied (line 199 commented out). This differs from appendix Eq5; the "
    "do-file is authoritative."
)


def _exp_change_one_category(cfg, app: str) -> pd.DataFrame:
    """Build the raw occupation-year exposure-change panel for one app category.

    Returns columns [occ_code_onet, occ_title_onet, occ_code_soc, year, exp_change]
    where exp_change is the un-discounted Delta e_ot (group-summed weighted element
    impact), one row per (occ, year) present for this category.

    Mirrors do-file lines 48-141: the per-year loop, the two merges, the by-ability
    and by-occupation sums, the dedup to occupation level, and the append over years.
    """
    slopes = pd.read_parquet(cfg.out_file(f"slopes_slimmed_{app}.parquet"))
    mm = pd.read_parquet(cfg.out_file("mapping_matrix_long_combined_frs18_frs21.parquet"))
    abilities = pd.read_parquet(cfg.out_file("onet_abilities_weighted.parquet")).copy()

    # Re-derive element_impact (= r_oj) under Stata's float32 storage discipline.
    # The Stage 1 checkpoint stores element_impact in float64, computed in float64,
    # so its low bits differ from Stata's value by ~1e-9 and flip a float32 ULP in
    # ~40% of cells. In Stata, element_impact is a `gen`/`egen` chain over the
    # float32-stored level_scaled and importance_scaled, so it is itself float32.
    # level_scaled and importance_scaled ARE float32-exact in the checkpoint, so
    # rebuilding element_impact = f32(level*imp) / f32(sum-by-occ), each step stored
    # float32, reproduces Stata's element_impact bit-for-bit (verified: 0 mismatch).
    # Without this, the per-element 1-ULP errors accumulate across the many
    # applications summed for the composite categories (allapps/redux) and are then
    # amplified by the square-and-scale-up step into ~1e-5 deviations.
    ei_old = _f32(_f32(abilities["level_scaled"]) * _f32(abilities["importance_scaled"]))
    abilities["_ei_old"] = ei_old
    ei_old_sum = _f32(so.group_total(abilities, "occ_code_onet", "_ei_old"))
    abilities["element_impact"] = _f32(ei_old / ei_old_sum)
    abilities = abilities.drop(columns="_ei_old")

    # MM_relevance = relevance_frs18, EXCEPT robotics uses our AIEL scores (line 76-77).
    # `gen MM_relevance` stores as float32 even though the source is double.
    mm = mm.copy()
    mm["MM_relevance"] = mm["relevance_frs18"]
    robotics = mm["application"] == "robotics"
    mm.loc[robotics, "MM_relevance"] = mm.loc[robotics, "relevance_aiel"]
    mm["MM_relevance"] = _f32(mm["MM_relevance"])

    per_year: list[pd.DataFrame] = []
    for year in cfg.years:
        # --- keep only this year's progress scores (line 57) ---
        sl_y = slopes.loc[slopes["year"] == year, ["application", "mean"]].copy()
        if sl_y.empty:
            # do-file skips the whole year when there are no observations (line 59).
            continue
        sl_y = sl_y.rename(columns={"mean": "application_progress_score"})
        # slopes `mean` is stored float32; carry that precision in.
        sl_y["application_progress_score"] = _f32(sl_y["application_progress_score"])

        # --- Eq2: AI impact on each ability (lines 64-91) ---
        # merge 1:m application using mapping matrix; keep matches only (_merge==3).
        merged = sl_y.merge(mm, on="application", how="inner")
        # MMscore = MM_relevance * application_progress_score, summed by ability.
        # `gen MMscore` -> float32; `egen ai_impact_on_ability = sum(.)` -> float32.
        merged["mmscore"] = _f32(merged["MM_relevance"] * merged["application_progress_score"])
        merged["ai_impact_on_ability"] = _f32(so.group_total(merged, "ability", "mmscore"))
        # collapse (first) ai_impact_on_ability, by(ability) -> one row per ability.
        score_matrix = (
            merged[["ability", "ai_impact_on_ability"]]
            .drop_duplicates("ability")
            .reset_index(drop=True)
        )

        # --- Eq3: occupation exposure change (lines 100-121) ---
        # merge m:1 ability: keep all O*NET ability rows; abilities absent from the
        # score matrix get ai_impact_on_ability = NaN (treated as 0 in the sum below).
        occ = abilities.merge(score_matrix, on="ability", how="left")
        # element_impact is stored float32; `gen weighted` and `egen sum` -> float32.
        occ["weighted"] = _f32(_f32(occ["element_impact"]) * occ["ai_impact_on_ability"])
        # egen sum, by(occ_code_onet): Stata treats the NaN contributions as 0.
        occ["exp_change_onet"] = _f32(so.group_total(occ, "occ_code_onet", "weighted"))
        # duplicates drop occ_code_onet Title exp_change_onet -> one row per occ.
        occ_lvl = occ[["occ_code_onet", "Title", "exp_change_onet"]].drop_duplicates(
            "occ_code_onet"
        )
        occ_lvl = occ_lvl.copy()
        occ_lvl["occ_code_soc"] = occ_lvl["occ_code_onet"].str[:7]
        occ_lvl["year"] = float(year)
        per_year.append(occ_lvl)

    panel = pd.concat(per_year, ignore_index=True)
    # drop if occ_code_soc=="" (line 140).
    panel = panel[panel["occ_code_soc"] != ""].reset_index(drop=True)
    panel = panel.rename(columns={"Title": "occ_title_onet", "exp_change_onet": "exp_change"})
    return panel


def _discount_square_scale(cfg, panel: pd.DataFrame, social: pd.DataFrame,
                           workctx: pd.DataFrame, app: str) -> pd.DataFrame:
    """Apply social discount, square, scale, cumulate, for one category panel.

    Mirrors do-file lines 145-223 (consequence-of-error discount intentionally
    NOT applied; see CODE_VS_APPENDIX).
    """
    occ_chars = cfg.occ_characteristic_cols  # social/cognitive/.../conseq_error
    social_cols = [c for c in occ_chars if c != "conseq_error"]

    # merge m:1 occ_code_onet: social skills + broad ability scores (lines 158-160).
    out = panel.merge(
        social[["occ_code_onet"] + social_cols], on="occ_code_onet", how="left"
    )

    # *** SOCIAL SKILLS DISCOUNTING (lines 169-181) ***
    # social_temp = (1 - social_skills) + social_weight; rescaled by the PANEL max.
    # Each gen/egen/replace stores float32; cast at every storage step.
    out["social_temp"] = _f32((1.0 - out["social_skills"]) + cfg.social_weight)
    social_temp_max = _f32(out["social_temp"].max())  # egen max() over ALL rows.
    out["social_score"] = _f32(out["social_temp"] / social_temp_max)
    out["exp_change"] = _f32(out["exp_change"] * out["social_score"])

    # *** CONSEQUENCE OF ERROR (lines 186-199) ***
    # conseq_error is merged in (it is an output column) but the discount is DISABLED.
    out = out.merge(
        workctx[["occ_code_onet", "conseq_error"]], on="occ_code_onet", how="left"
    )

    # Square (line 202), then scale up (line 207).
    out["exp_change"] = _f32(out["exp_change"] ** 2)
    out["exp_change"] = _f32(out["exp_change"] * cfg.scale_up)

    # Eq6: cumulative exposure by occupation over years (lines 210-211).
    # `gen exp_cumul = sum(exp_change)` stores the running total as float32.
    out["exp_cumul"] = _f32(so.cumsum_by(out, "occ_code_onet", "exp_change", "year"))

    # Tidy and rename to the category-specific output names (lines 222-223, 230-234).
    keep = [
        "occ_code_onet", "occ_title_onet", "exp_change", "exp_cumul", "year",
        "occ_code_soc",
    ] + occ_chars
    out = out[keep].rename(
        columns={"exp_change": f"exp_change_{app}", "exp_cumul": f"exp_cumul_{app}"}
    )
    return out


def build(cfg) -> dict[str, pd.DataFrame]:
    """Build every category panel and the merged preliminary panel.

    Returns a dict: {'<app>': <category panel>, 'preliminary': <merged panel>}.
    """
    social = pd.read_parquet(cfg.out_file("onet_social_skills_physical_abilities.parquet"))
    workctx = pd.read_parquet(cfg.out_file("onet_work_context.parquet"))

    panels: dict[str, pd.DataFrame] = {}
    for app in cfg.app_categories:
        raw = _exp_change_one_category(cfg, app)
        panels[app] = _discount_square_scale(cfg, raw, social, workctx, app)

    # --- COMBINE ALL SUB-INDICES (do-file lines 246-258) ---
    # Start from allapps (defines the row set and the occ-characteristic columns),
    # then merge each category's exp_change_*/exp_cumul_* 1:1 on (year, occ_code_onet).
    prelim = panels["allapps"].copy()
    for app in cfg.app_categories:
        if app == "allapps":
            continue
        cols = ["year", "occ_code_onet", f"exp_change_{app}", f"exp_cumul_{app}"]
        prelim = prelim.merge(
            panels[app][cols], on=["year", "occ_code_onet"], how="left", validate="1:1"
        )

    # Column order mirrors the do-file `order` (lines 255-257).
    occ_chars = cfg.occ_characteristic_cols
    front = ["occ_code_onet", "year", "occ_title_onet", "occ_code_soc"] + occ_chars
    change_cols = [f"exp_change_{a}" for a in cfg.app_categories]
    cumul_cols = [f"exp_cumul_{a}" for a in cfg.app_categories]
    prelim = prelim[front + change_cols + cumul_cols]

    panels["preliminary"] = prelim
    return panels


def run(cfg, validate: bool = True):  # noqa: A002 (param name mirrors stage API)
    """Build the panels, checkpoint the preliminary panel, and validate.

    Returns a list of CompareResult: [allapps, genai, preliminary].
    """
    panels = build(cfg)

    # Checkpoint the merged panel for Stage 5.
    out_path = cfg.out_file("daioe_panel_onet_preliminary.parquet")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    panels["preliminary"].to_parquet(out_path, index=False)

    if not validate:
        return []

    results = []

    # Numeric value columns to validate for each target. We pass these explicitly
    # rather than relying on the harness's auto-select, because string columns are
    # carried as pandas StringDtype here and the auto-select's np.issubdtype probe
    # cannot interpret that dtype. occ_code_soc/occ_title_onet are string keys and
    # excluded from the numeric comparison by construction.
    occ_chars = cfg.occ_characteristic_cols  # social/cognitive/.../conseq_error

    # allapps single-category panel.
    results.append(
        validate_mod.compare_to_dta(
            panels["allapps"],
            cfg.enriched_ref_file("daioe_panel_onet_allapps.dta"),
            keys=["occ_code_onet", "year"],
            value_cols=["exp_change_allapps", "exp_cumul_allapps"] + occ_chars,
            tol=cfg.tol_internal,
            name="daioe_panel_onet_allapps",
        )
    )

    # genai single-category panel.
    results.append(
        validate_mod.compare_to_dta(
            panels["genai"],
            cfg.enriched_ref_file("daioe_panel_onet_genai.dta"),
            keys=["occ_code_onet", "year"],
            value_cols=["exp_change_genai", "exp_cumul_genai"] + occ_chars,
            tol=cfg.tol_internal,
            name="daioe_panel_onet_genai",
        )
    )

    # Merged preliminary panel (PRIMARY): validate every exp_change_*/exp_cumul_*
    # plus the occupation-characteristic columns.
    prelim_value_cols = (
        occ_chars
        + [f"exp_change_{a}" for a in cfg.app_categories]
        + [f"exp_cumul_{a}" for a in cfg.app_categories]
    )
    results.append(
        validate_mod.compare_to_dta(
            panels["preliminary"],
            cfg.enriched_ref_file("daioe_panel_onet_preliminary.dta"),
            keys=["occ_code_onet", "year"],
            value_cols=prelim_value_cols,
            tol=cfg.tol_internal,
            name="daioe_panel_onet_preliminary",
        )
    )

    return results
