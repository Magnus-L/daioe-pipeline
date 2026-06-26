"""Stage 3 — Felten mapping matrix x_ij (fixed application-ability relevance).

This stage rebuilds the long, combined application-ability mapping matrix that
underlies the Felten/AIOE construction. Each AI *application* (e.g. "image
recognition", "robotics") is mapped onto each of the 52 O*NET *abilities* with a
0..1 relevance score. We carry three independent score columns:

  - relevance_frs18  : Felten, Raj & Seamans (2018) expert mapping (16 apps)
  - relevance_frs21  : Felten, Raj & Seamans (2021) Mechanical-Turk mapping (10 apps)
  - relevance_aiel   : our own (AI-Econ Lab) robotics mapping (1 app)

The three source matrices share the same 52 abilities but cover different (and
only partly overlapping) sets of applications, so the combined long matrix is the
union over applications: 18 applications x 52 abilities = 936 rows.

Authoritative source: Code/1_1_mapping_matrices.do. This module mirrors that
do-file exactly; the do-file wins over any prose summary.
"""
from __future__ import annotations

import pandas as pd

from . import io
from . import validate as validate_mod

# The 52 O*NET abilities, in the *exact* order the Stata loop appends them.
# In the do-file the long matrices are built by appending each ability in turn,
# so the on-disk ordering is irrelevant for the merge keys; we only need the set
# and the canonical (no-space, no-hyphen) spelling that the loop variable names use.
ABILITIES = [
    "oralcomprehension", "writtencomprehension", "oralexpression", "writtenexpression",
    "fluencyofideas", "originality", "problemsensitivity", "deductivereasoning",
    "inductivereasoning", "informationordering", "categoryflexibility",
    "mathematicalreasoning", "numberfacility", "memorization", "speedofclosure",
    "flexibilityofclosure", "perceptualspeed", "spatialorientation", "visualization",
    "selectiveattention", "timesharing", "armhandsteadiness", "manualdexterity",
    "fingerdexterity", "controlprecision", "multilimbcoordination",
    "responseorientation", "ratecontrol", "reactiontime", "wristfingerspeed",
    "speedoflimbmovement", "staticstrength", "explosivestrength", "dynamicstrength",
    "trunkstrength", "stamina", "extentflexibility", "dynamicflexibility",
    "grossbodycoordination", "grossbodyequilibrium", "nearvision", "farvision",
    "visualcolordiscrimination", "nightvision", "peripheralvision", "depthperception",
    "glaresensitivity", "hearingsensitivity", "auditoryattention", "soundlocalization",
    "speechrecognition", "speechclarity",
]
assert len(ABILITIES) == 52

# FRS18: q values (original excel row order) of the nine applications we "use".
# Stata: replace used_application = 1 if inlist(q,1,2,3,4,6,7,8,10,11)
FRS18_USED_Q = {1, 2, 3, 4, 6, 7, 8, 10, 11}

# FRS21: application_id values of the nine "used" applications in the mturk file.
# Stata: replace used_application = 1 if inlist(application_id,1,2,3,4,5,6,7,8,9)
FRS21_USED_ID = {1, 2, 3, 4, 5, 6, 7, 8, 9}


def _canon_ability(name: str) -> str:
    """Mirror Stata's ability-name normalisation: drop spaces and hyphens.

    Stata's `import excel, firstrow` strips spaces/special chars from header names
    (so "oral comprehension" -> oralcomprehension), and for the robotics matrix the
    do-file does `subinstr(ability," ","")` and `subinstr(ability,"-","")`. Both
    paths yield the same canonical spelling, which is what the merge keys on.
    """
    return name.replace(" ", "").replace("-", "")


def _build_frs18(cfg) -> pd.DataFrame:
    """FRS18 mapping matrix -> long (application, ability, relevance_frs18).

    Steps mirror the do-file:
      1. import the 'Combined' sheet (16 apps x 52 ability columns + q + abilities);
      2. assign application_id: the nine 'used' apps (q in FRS18_USED_Q) come first,
         ordered alphabetically by application, then the remaining seven, also alpha,
         with ids 10..16;
      3. reshape wide -> long over the 52 abilities.
    """
    df = io.read_excel_sheet(cfg.raw_file("mapping_matrix_frs18.xlsx"), "Combined")
    # Header names arrive with spaces/leading whitespace; normalise to canonical.
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={"abilities": "application"})
    # Canonicalise the 52 ability columns to no-space/no-hyphen spelling.
    rename_abilities = {
        c: _canon_ability(c) for c in df.columns if c not in ("q", "application")
    }
    df = df.rename(columns=rename_abilities)

    # --- application_id assignment (do-file lines 16-22) ---
    df["used_application"] = df["q"].isin(FRS18_USED_Q).astype(int)
    # gsort -used_application application  ==> used first, then alphabetical by app.
    df = df.sort_values(
        ["used_application", "application"], ascending=[False, True]
    ).reset_index(drop=True)
    df["application_id"] = df.index + 1  # _n

    # --- reshape wide -> long ---
    long = df.melt(
        id_vars=["application_id", "application"],
        value_vars=ABILITIES,
        var_name="ability",
        value_name="relevance_frs18",
    )
    return long[["application_id", "application", "ability", "relevance_frs18"]]


def _build_frs21(cfg) -> pd.DataFrame:
    """FRS21 mturk matrix -> long (application, ability, relevance_frs21).

    Note: the do-file rebuilds application_id here (used apps 1..9 alpha first, then
    instrumental track recognition forced to 17), but the *combined* long matrix is
    merged on (application, ability) and drops frs21's application_id, so the id is
    irrelevant downstream. We therefore only need application, ability, relevance.
    """
    df = io.read_dta(cfg.raw_file("mturk_mapping_matrix_frs21.dta"))
    df = df.rename(columns={"applications": "application"})
    # Ability columns are already no-space; canonicalise defensively anyway.
    rename_abilities = {
        c: _canon_ability(c)
        for c in df.columns
        if c not in ("application_id", "application")
    }
    df = df.rename(columns=rename_abilities)

    long = df.melt(
        id_vars=["application"],
        value_vars=ABILITIES,
        var_name="ability",
        value_name="relevance_frs21",
    )
    return long[["application", "ability", "relevance_frs21"]]


def _build_aiel(cfg) -> pd.DataFrame:
    """Robotics (AIEL) matrix -> long (application='robotics', ability, relevance_aiel).

    The ROE excel lists ~19 physical/psychomotor abilities with a relevance score in
    the first two columns and *no header row* (Stata: `import excel ... clear` reads
    A/B and treats the first row as data). We extract the ability name from each
    question ("...used for <ability>*..."), canonicalise it, then fill the remaining
    abilities (the cognitive/sensory ones, absent from the robotics survey) with 0.
    """
    # header=None: the first spreadsheet row is data (arm-hand steadiness, 0.75),
    # not a header. read_excel_sheet uses pandas' default header=0, which would eat
    # that first ability, so we read the raw file directly here.
    raw = pd.read_excel(
        cfg.raw_file("ROE-mapping-matrix.xlsx"),
        sheet_name="Ability mapping matrix",
        header=None,
    )
    raw = raw.rename(columns={0: "question", 1: "relevance_aiel"})
    # Stata: drop if question==""  (empty question rows).
    raw = raw[raw["question"].astype(str).str.strip() != ""].copy()

    # Extract ability name: substring after "used for " up to the first "*".
    def extract(q: str) -> str:
        pos = q.find("used for ")
        tail = q[pos + len("used for "):] if pos >= 0 else q
        return tail.split("*")[0]

    raw["ability"] = raw["question"].astype(str).map(extract).map(_canon_ability)
    aiel = raw[["ability", "relevance_aiel"]].copy()

    # Merge against the full 52-ability set; abilities absent from the robotics
    # survey get relevance_aiel = 0 (do-file: replace relevance_aiel = 0 if missing).
    full = pd.DataFrame({"ability": ABILITIES})
    aiel = full.merge(aiel, on="ability", how="left", validate="1:1")
    aiel["relevance_aiel"] = aiel["relevance_aiel"].fillna(0.0)
    aiel["application"] = "robotics"
    return aiel[["application", "ability", "relevance_aiel"]]


def build(cfg) -> pd.DataFrame:
    """Combine the three long matrices on (application, ability).

    Mirrors do-file section 3: start from frs18 long, merge frs21 long (1:1), then
    merge aiel long (1:1). This is a union over applications (18 apps x 52 = 936 rows):
    frs18 covers 16 apps, frs21 adds instrumental track recognition, aiel adds robotics.
    application_id is carried only from frs18, so it is missing for the two
    frs21-/aiel-only applications.
    """
    frs18 = _build_frs18(cfg)
    frs21 = _build_frs21(cfg)
    aiel = _build_aiel(cfg)

    # 1:1 outer merges (Stata default merge keeps all master+using rows).
    combined = frs18.merge(
        frs21, on=["application", "ability"], how="outer", validate="1:1"
    )
    combined = combined.merge(
        aiel, on=["application", "ability"], how="outer", validate="1:1"
    )

    return combined[
        [
            "application_id",
            "application",
            "ability",
            "relevance_frs18",
            "relevance_frs21",
            "relevance_aiel",
        ]
    ]


def run(cfg, validate: bool = True):  # noqa: A002 (param name mirrors stage API)
    """Build the combined mapping matrix, checkpoint it, and validate.

    Returns a list of CompareResult (one target).
    """
    combined = build(cfg)

    # Checkpoint for downstream stages.
    out_path = cfg.out_file("mapping_matrix_long_combined_frs18_frs21.parquet")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(out_path, index=False)

    if not validate:
        return []

    res = validate_mod.compare_to_dta(
        combined,
        cfg.enriched_ref_file("mapping_matrix_long_combined_frs18_frs21.dta"),
        keys=["application", "ability"],
        value_cols=["relevance_frs18", "relevance_frs21", "relevance_aiel"],
        tol=cfg.tol_internal,
        name="mapping_matrix_long_combined_frs18_frs21",
    )
    return [res]
