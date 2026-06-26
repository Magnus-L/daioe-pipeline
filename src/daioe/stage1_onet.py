"""Stage 1 -- O*NET inputs for the DAIOE index.

Reproduces Code/1_1_onet_data.do. Three checkpoints are produced from the raw
O*NET Excel files:

  (a) onet_abilities_weighted   -- one row per (occupation, ability element).
        element_impact = r_oj, the per-occupation weight on each ability that the
        DAIOE index later interacts with each AI application's ability-coverage.
        Recipe: scale importance by /5 and level by /7 (their natural maxima),
        take their product per (occ, ability), then renormalise so the products
        sum to one within each occupation.

  (b) onet_skills_weighted      -- one row per (occupation, skill), with a
        skill_type. The six social skills (ElementID 2.B.1.a..2.B.1.f) feed S_o.

  (c) onet_social_skills_physical_abilities -- one row per occupation (966).
        social_skills = S_o = sum over the six social skills of level*importance,
        then rescaled so the top occupation scores 1. The same max-rescaling is
        applied to five ability-type sums (cognitive / psychomotor / physical /
        sensory / phys+psychom). conseq_error (from Work Context) is built as a
        separate checkpoint: the Stata do-file does NOT merge it into this file.

Economic intuition: r_oj answers "how much does ability j matter for occupation
o?" as a probability-weight vector; S_o and the ability-type sums summarise an
occupation's reliance on social vs physical/cognitive content, used downstream to
discount AI exposure where human-specific (social) content dominates.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from . import io, stata_ops as so, validate

# ----------------------------------------------------------------------------- helpers

# Stata's `import excel, firstrow` turns a header label into a variable name by
# dropping every character that is not a letter, digit or underscore. We mirror
# that so e.g. "O*NET-SOC Code" -> "ONETSOCCode", "Element ID" -> "ElementID".
_STATA_NAME_STRIP = re.compile(r"[^A-Za-z0-9_]")


def _stata_varname(label: str) -> str:
    return _STATA_NAME_STRIP.sub("", str(label))


def _read_onet_excel(path, sheet: str) -> pd.DataFrame:
    """Read an O*NET sheet and rename columns to Stata firstrow conventions."""
    df = io.read_excel_sheet(path, sheet)
    df = df.rename(columns={c: _stata_varname(c) for c in df.columns})
    return df


def _clean_name(s: pd.Series) -> pd.Series:
    """lower(); remove spaces and hyphens -- Stata subinstr cleaning of names."""
    return (
        s.astype(str)
        .str.lower()
        .str.replace(" ", "", regex=False)
        .str.replace("-", "", regex=False)
    )


# --------------------------------------------------------------- abilities metadata
def _build_abilities_metadata(cfg) -> pd.DataFrame:
    """Reproduce onet_abilities_metadata_all_levels: for each ability ElementName,
    its cleaned `ability`, plus ability_type / ability_type2 (and descriptions),
    derived purely from Abilities_Competencies.xlsx.

    The do-file imports with firstrow (so the first sheet row becomes the variable
    names A,B,C,...), then `drop if _n<=3` removes the two banner rows plus the
    "Element ID / Element Name / ..." header row. The remaining rows are the model
    hierarchy: 5-char codes are ability *types* (1.A.1), 7-char are sub-types
    (1.A.1.a), 9-char are the abilities themselves (1.A.1.a.1).
    """
    raw = io.read_excel_sheet(cfg.raw_file("Abilities_Competencies.xlsx"), "Abilities")
    # `firstrow`: first row is the header; pandas already consumed it as columns.
    # Stata columns become A (col0), B (col1), C (col2), ...
    raw = raw.rename(
        columns={c: chr(ord("A") + i) for i, c in enumerate(raw.columns)}
    )
    # `drop if _n<=3`: pandas already dropped row 0 (header) -> drop the next 3.
    raw = raw.iloc[3:].reset_index(drop=True)

    code = raw["A"].astype(str)
    strlen = code.str.len()

    # Ability TYPES (strlen==5): code 1.A.1 etc.
    types = raw[strlen == 5][["A", "B", "C"]].copy()
    types.columns = ["ability_type_code", "ability_type", "ability_type_description"]

    # Ability SUB-TYPES "type2" (strlen==7): code 1.A.1.a etc.
    types2 = raw[strlen == 7][["A", "B", "C"]].copy()
    types2.columns = ["ability_type2_code", "ability_type2", "ability_type2_description"]
    types2["ability_type_code"] = types2["ability_type2_code"].str.slice(0, 5)

    # ABILITIES (strlen==9): code 1.A.1.a.1 etc.
    ab = raw[strlen == 9][["A", "B", "C"]].copy()
    ab.columns = ["ability_code", "ElementName", "ability_description"]
    # cleaned ability name; ElementName keeps the original (matches other O*NET files)
    ab["ability"] = _clean_name(ab["ElementName"])
    ab["ability_type_code"] = ab["ability_code"].str.slice(0, 5)
    ab["ability_type2_code"] = ab["ability_code"].str.slice(0, 7)

    # merge m:1 on the two code levels (assert(3) in Stata == inner, perfect merge).
    # types2 carries its own ability_type_code derived from the sub-type code; drop
    # it before merging so we keep ab's copy and avoid a _x/_y suffix collision.
    meta = ab.merge(
        types2.drop(columns=["ability_type_code"]),
        on="ability_type2_code",
        how="inner",
        validate="m:1",
    )
    meta = meta.merge(
        types[["ability_type_code", "ability_type", "ability_type_description"]],
        on="ability_type_code",
        how="inner",
        validate="m:1",
    )
    return meta


# --------------------------------------------------------------- (a) abilities_weighted
def _build_abilities_weighted(cfg) -> pd.DataFrame:
    """Reproduce onet_abilities_weighted.dta (element_impact = r_oj)."""
    ab = _read_onet_excel(cfg.raw_file("Abilities_Onet_Feb2018_22_2.xlsx"), "Abilities")
    ab = ab.rename(columns={"ONETSOCCode": "occ_code_onet"})

    meta = _build_abilities_metadata(cfg)
    # merge m:1 ElementName, keepusing(ability ability_description ability_type
    # ability_type2 ability_type_description), assert(3) -> inner, perfect.
    keep_meta = [
        "ElementName",
        "ability",
        "ability_description",
        "ability_type",
        "ability_type2",
        "ability_type_description",
    ]
    ab = ab.merge(meta[keep_meta], on="ElementName", how="inner", validate="m:1")

    # scaled scores: importance is 0-5, level is 0-7; divide by the natural max.
    # Stata stores every gen/egen here as `float` (single). The do-file evaluates
    # DataValue/5 and DataValue/7 in double, then stores the result float32; we
    # mirror that by computing in float64 and so.f32() the stored column. Each
    # downstream product/sum then consumes the float32-rounded operand, exactly as
    # Stata's single-precision chain does (a pure-float64 chain drifts ~1e-7/step).
    ab["scale_importance"] = so.f32(
        np.where(ab["ScaleName"] == "Importance", ab["DataValue"] / 5.0, np.nan)
    )
    ab["scale_level"] = so.f32(
        np.where(ab["ScaleName"] == "Level", ab["DataValue"] / 7.0, np.nan)
    )

    grp = ["occ_code_onet", "ElementID"]
    # egen ..max.. by(occ,ElementID): collapse the Importance row and Level row
    # (which are separate rows) onto one value per ability. NaN-safe max. egen max
    # over a float32 column returns a float32; so.f32 the broadcast result.
    ab["level_scaled"] = so.f32(ab.groupby(grp)["scale_level"].transform("max"))
    ab["importance_scaled"] = so.f32(ab.groupby(grp)["scale_importance"].transform("max"))

    # "_new" per-occupation weight versions (carried for parity; NOT used in product).
    # egen sum() accumulates the float32 scores in a double accumulator then stores
    # float32; sum a float64 VIEW of the float32 column (not float32-native, which
    # would lose a ULP) and so.f32 the total. Each ratio is gen in double, stored f32.
    ab["importance_sum"] = so.f32(
        ab.assign(_si=ab["scale_importance"].astype("float64"))
        .groupby("occ_code_onet")["_si"].transform("sum")
    )
    ab["importance_scaled_temp"] = so.f32(
        ab["scale_importance"].astype("float64") / ab["importance_sum"].astype("float64")
    )
    ab["importance_scaled_new"] = so.f32(ab.groupby(grp)["importance_scaled_temp"].transform("max"))
    ab["level_sum"] = so.f32(
        ab.assign(_sl=ab["scale_level"].astype("float64"))
        .groupby("occ_code_onet")["_sl"].transform("sum")
    )
    ab["level_scaled_temp"] = so.f32(
        ab["scale_level"].astype("float64") / ab["level_sum"].astype("float64")
    )
    ab["level_scaled_new"] = so.f32(ab.groupby(grp)["level_scaled_temp"].transform("max"))

    # keep needed vars + drop duplicates (the Importance/Level rows collapse to one).
    keep = [
        "occ_code_onet",
        "Title",
        "ElementID",
        "ability",
        "ability_type",
        "ability_type2",
        "ability_description",
        "ability_type_description",
        "level_scaled",
        "importance_scaled",
        "importance_scaled_new",
        "level_scaled_new",
        "ElementName",
    ]
    ab = ab[keep].drop_duplicates().reset_index(drop=True)

    # element_impact_old = level_scaled*importance_scaled (FRS18 weight),
    # then renormalise so the products sum to 1 within each occupation. The product
    # multiplies two float32-stored columns; Stata evaluates it in double and stores
    # the result float32, so promote both operands to a float64 view, multiply, then
    # so.f32. egen sum() again accumulates in double over the float32 column (sum a
    # float64 view, then so.f32). Doing this upstream makes element_impact bit-exact
    # so Stage 4 need not re-derive it (its r_oj feeds the squared, x10, cumulated
    # index where a 1-ULP error in any element amplifies to ~1e-5 over 12 years).
    ei_old = so.f32(
        ab["level_scaled"].astype("float64") * ab["importance_scaled"].astype("float64")
    )
    ab["element_impact_old"] = ei_old
    ab["element_impact_old_sum"] = so.f32(
        ab.assign(_eio=ei_old.astype("float64"))
        .groupby("occ_code_onet")["_eio"].transform("sum")
    )
    ab["element_impact"] = so.f32(
        ab["element_impact_old"].astype("float64")
        / ab["element_impact_old_sum"].astype("float64")
    )
    ab = ab.drop(columns=["element_impact_old", "element_impact_old_sum"])

    # column order to match the .dta (Title, ElementName placement etc.)
    cols = [
        "occ_code_onet",
        "Title",
        "ElementID",
        "ElementName",
        "ability_type",
        "ability_type2",
        "ability",
        "ability_description",
        "ability_type_description",
        "level_scaled",
        "importance_scaled",
        "importance_scaled_new",
        "level_scaled_new",
        "element_impact",
    ]
    return ab[cols]


# --------------------------------------------------------------- (b) skills_weighted
def _build_skills_weighted(cfg) -> pd.DataFrame:
    """Reproduce onet_skills_weighted.dta (with skill_type)."""
    sk = _read_onet_excel(cfg.raw_file("Skills_Onet_Feb2018_22_2.xlsx"), "Skills")
    sk = sk.rename(columns={"ONETSOCCode": "occ_code_onet", "Title": "occ_title_onet"})
    sk["skill"] = _clean_name(sk["ElementName"])

    # split level (/7) and importance (/5) out of the single DataValue column.
    # `gen level_temp`/`importance_temp` store float32; compute in double, so.f32.
    sk["level_temp"] = so.f32(
        np.where(sk["ScaleName"] == "Level", sk["DataValue"] / 7.0, np.nan)
    )
    sk["importance_temp"] = so.f32(
        np.where(sk["ScaleName"] == "Importance", sk["DataValue"] / 5.0, np.nan)
    )

    # collapse (first) occ_title ElementName ElementID (max) level importance, by(occ,skill)
    # collapse (max) of a float32 source keeps float32; so.f32 the collapsed columns.
    g = sk.groupby(["occ_code_onet", "skill"], sort=False)
    coll = g.agg(
        occ_title_onet=("occ_title_onet", "first"),
        ElementName=("ElementName", "first"),
        ElementID=("ElementID", "first"),
        level=("level_temp", "max"),
        importance=("importance_temp", "max"),
    ).reset_index()
    coll["level"] = so.f32(coll["level"])
    coll["importance"] = so.f32(coll["importance"])

    # impact = level*importance, renormalised to sum 1 per occupation. Product of two
    # float32 columns: evaluate in a float64 view then so.f32. egen sum accumulates in
    # double over the float32 column (sum a float64 view), then so.f32; ratio likewise.
    skill_impact_unscaled = so.f32(
        coll["level"].astype("float64") * coll["importance"].astype("float64")
    )
    coll["skill_impact_unscaled"] = skill_impact_unscaled
    coll["skill_impact_sum"] = so.f32(
        coll.assign(_siu=skill_impact_unscaled.astype("float64"))
        .groupby("occ_code_onet")["_siu"].transform("sum")
    )
    coll["skill_impact"] = so.f32(
        coll["skill_impact_unscaled"].astype("float64")
        / coll["skill_impact_sum"].astype("float64")
    )
    coll = coll.drop(columns=["skill_impact_unscaled", "skill_impact_sum"])

    # assign the six O*NET skill categories.
    skill_type_map = {
        "Basic skills": [
            "activelearning", "activelistening", "criticalthinking", "learningstrategies",
            "mathematics", "monitoring", "readingcomprehension", "science", "speaking", "writing",
        ],
        "Social skills": [
            "coordination", "instructing", "negotiation", "persuasion",
            "serviceorientation", "socialperceptiveness",
        ],
        "Complex problem solving skills": ["complexproblemsolving"],
        "Technical skills": [
            "equipmentmaintenance", "equipmentselection", "installation", "operationandcontrol",
            "operationsanalysis", "operationmonitoring", "programming", "qualitycontrolanalysis",
            "repairing", "technologydesign", "troubleshooting",
        ],
        "Systems skills": ["judgmentanddecisionmaking", "systemsanalysis", "systemsevaluation"],
        "Resource management skills": [
            "managementoffinancialresources", "managementofmaterialresources",
            "managementofpersonnelresources", "timemanagement",
        ],
    }
    lookup = {s: t for t, lst in skill_type_map.items() for s in lst}
    coll["skill_type"] = coll["skill"].map(lookup).fillna("")
    return coll


# ----------------------------------------------- (c) social skills + ability-type sums
SOCIAL_ELEMENT_IDS = [
    "2.B.1.a", "2.B.1.b", "2.B.1.c", "2.B.1.d", "2.B.1.e", "2.B.1.f",
]


def _build_social_and_abilities(skills_weighted, abilities_weighted) -> pd.DataFrame:
    """Reproduce onet_social_skills_physical_abilities.dta (without conseq_error,
    which the Stata do-file leaves out of this particular file)."""
    # --- social skills: sum of level*importance over the six social skills ---
    # `gen social_skills_temp = level*importance` multiplies two float32-stored
    # columns; Stata evaluates the product in double and stores float32. We promote
    # to a float64 view, multiply, then so.f32. The subsequent `collapse (sum)`
    # accumulates these float32 values in a double accumulator and stores the result
    # as `double` (onet_social_skills_physical_abilities.dta has social_skills double),
    # so we sum a float64 view and KEEP it double (no f32 on the sum).
    sk = skills_weighted.copy()
    sk["social_skills_temp"] = so.f32(
        np.where(
            sk["skill_type"] == "Social skills",
            sk["level"].astype("float64") * sk["importance"].astype("float64"),
            np.nan,
        )
    )
    social = (
        sk.assign(_t=sk["social_skills_temp"].astype("float64"))
        .groupby("occ_code_onet", sort=False)["_t"]
        .sum(min_count=0)  # collapse (sum): double accumulator, missing treated as 0
        .reset_index(name="social_skills")
    )

    # --- the four/five ability-type sums (level_scaled*importance_scaled) ---
    # Each `gen *_temp = level_scaled*importance_scaled` is float32 (double product of
    # float32 operands, stored float32). The `collapse (sum)` again stores `double`.
    ab = abilities_weighted.copy()
    prod = so.f32(
        ab["level_scaled"].astype("float64") * ab["importance_scaled"].astype("float64")
    )
    is_phys = ab["ability_type"] == "Physical Abilities"
    is_psy = ab["ability_type"] == "Psychomotor Abilities"
    ab["phys_psychom_abilities_temp"] = so.f32(np.where(is_phys | is_psy, prod.astype("float64"), np.nan))
    ab["physical_abilities_temp"] = so.f32(np.where(is_phys, prod.astype("float64"), np.nan))
    ab["psychomotor_abilities_temp"] = so.f32(np.where(is_psy, prod.astype("float64"), np.nan))
    ab["cognitive_abilities_temp"] = so.f32(
        np.where(ab["ability_type"] == "Cognitive Abilities", prod.astype("float64"), np.nan)
    )
    ab["sensory_abilities_temp"] = so.f32(
        np.where(ab["ability_type"] == "Sensory Abilities", prod.astype("float64"), np.nan)
    )

    # collapse (sum): accumulate a float64 view of each float32 _temp; result is double.
    g = ab.assign(
        **{c: ab[c].astype("float64") for c in [
            "phys_psychom_abilities_temp", "physical_abilities_temp",
            "psychomotor_abilities_temp", "cognitive_abilities_temp",
            "sensory_abilities_temp",
        ]}
    ).groupby("occ_code_onet", sort=False)
    abil = g.agg(
        phys_psychom_abilities=("phys_psychom_abilities_temp", lambda s: s.sum(min_count=0)),
        physical_abilities=("physical_abilities_temp", lambda s: s.sum(min_count=0)),
        psychomotor_abilities=("psychomotor_abilities_temp", lambda s: s.sum(min_count=0)),
        cognitive_abilities=("cognitive_abilities_temp", lambda s: s.sum(min_count=0)),
        sensory_abilities=("sensory_abilities_temp", lambda s: s.sum(min_count=0)),
        occ_title_onet=("Title", "first"),
    ).reset_index()

    # merge 1:1 occ_code_onet (abilities is the master; social is the using file)
    out = abil.merge(social, on="occ_code_onet", how="left", validate="1:1")

    # Rescale each variable so the leading occupation scores 1. This is the step that
    # leaves the reference max at 0.99999998, NOT 1.0: in Stata the collapsed sum is
    # stored `double`, but `egen max_value = max(var)` reads the variable's stored
    # value and `max_value` is itself a `float` (single). So the denominator is the
    # float32-ROUNDED maximum of the double sums, while the numerator stays the full
    # double sum; `replace var = var/max_value` then divides double by float32-max in
    # double and stores double. Mirror this exactly: numerator = double sum, denominator
    # = so.f32(max of the double sum), division in float64. A pure-float64 chain (divide
    # by the unrounded max) would give the leader exactly 1.0 and miss this sub-ULP
    # residual, which Stage 4 amplifies past 1e-6 when it squares, x10s, and cumulates.
    for var in [
        "phys_psychom_abilities", "physical_abilities", "psychomotor_abilities",
        "cognitive_abilities", "sensory_abilities", "social_skills",
    ]:
        max_value = np.float64(so.f32(out[var].max()))  # egen max() stored float (single)
        out[var] = out[var].astype("float64") / max_value

    cols = [
        "occ_code_onet", "occ_title_onet", "social_skills", "cognitive_abilities",
        "psychomotor_abilities", "sensory_abilities", "physical_abilities",
        "phys_psychom_abilities",
    ]
    return out[cols]


def _build_work_context(cfg) -> pd.DataFrame:
    """conseq_error (and degree_autom) per occupation from Work Context.
    Kept as a separate checkpoint: the do-file saves it to onet_work_context.dta and
    does not merge conseq_error into the social-skills file."""
    wc = _read_onet_excel(
        cfg.raw_file("Work_Context_Onet_Feb2018_22_2.xlsx"), "Work Context"
    )
    # keep the occupation-level overall scores (ScaleID=="CX") for the two elements.
    mask = (wc["ScaleID"] == "CX") & wc["ElementName"].isin(
        ["Consequence of Error", "Degree of Automation"]
    )
    wc = wc[mask].copy()
    wc["ElementName"] = wc["ElementName"].replace(
        {"Consequence of Error": "conseq_error", "Degree of Automation": "degree_autom"}
    )
    wide = (
        wc.pivot_table(
            index=["ONETSOCCode", "Title"],
            columns="ElementName",
            values="DataValue",
            aggfunc="first",
        )
        .reset_index()
        .rename_axis(columns=None)
        .rename(columns={"ONETSOCCode": "occ_code_onet", "Title": "occ_title_onet"})
    )
    return wide[["occ_code_onet", "occ_title_onet", "conseq_error", "degree_autom"]]


# ----------------------------------------------------------------------------- run
def run(cfg, validate: bool = True):
    """Build the three Stage 1 checkpoints and validate against the Stata .dta refs.

    Returns the list of CompareResults (empty list-friendly if validate=False)."""
    from . import validate as _v  # local alias; `validate` arg shadows the module name

    abilities_weighted = _build_abilities_weighted(cfg)
    skills_weighted = _build_skills_weighted(cfg)
    work_context = _build_work_context(cfg)
    social_abilities = _build_social_and_abilities(skills_weighted, abilities_weighted)

    # write checkpoints downstream stages consume.
    cfg.out_file("onet_abilities_weighted.parquet").parent.mkdir(parents=True, exist_ok=True)
    abilities_weighted.to_parquet(cfg.out_file("onet_abilities_weighted.parquet"))
    skills_weighted.to_parquet(cfg.out_file("onet_skills_weighted.parquet"))
    work_context.to_parquet(cfg.out_file("onet_work_context.parquet"))
    social_abilities.to_parquet(cfg.out_file("onet_social_skills_physical_abilities.parquet"))

    if not validate:
        return []

    results = []
    results.append(
        _v.compare_to_dta(
            abilities_weighted,
            cfg.enriched_ref_file("onet_abilities_weighted.dta"),
            keys=["occ_code_onet", "ElementID"],
            value_cols=["element_impact", "level_scaled", "importance_scaled"],
            tol=cfg.tol_internal,
            name="onet_abilities_weighted",
        )
    )
    # NOTE: the Stata ref file does NOT contain conseq_error, so it is excluded from
    # this comparison (it lives in onet_work_context.dta instead).
    results.append(
        _v.compare_to_dta(
            social_abilities,
            cfg.enriched_ref_file("onet_social_skills_physical_abilities.dta"),
            keys=["occ_code_onet"],
            value_cols=[
                "social_skills", "cognitive_abilities", "psychomotor_abilities",
                "sensory_abilities", "physical_abilities", "phys_psychom_abilities",
            ],
            tol=cfg.tol_internal,
            name="onet_social_skills_physical_abilities",
        )
    )
    return results
