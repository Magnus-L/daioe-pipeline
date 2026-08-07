"""
test_against_engberg.py — check the vintage variants against Engberg (2026), "Social Computers?".

Essay IV of Erik's thesis is the best available external evidence on which social tasks LLMs
actually reach, and it is evidence our own measure has to answer to. Two of its results are precise
enough to test a candidate DAIOE variant against directly.

**Test 1, the hump (his Table 3).** Regressing z-standardised LLM exposure on social skill intensity
and its square, he finds for DAIOE-LM a coefficient of 12.18 on intensity and -7.575 on its square,
implying exposure peaks at intensity 0.80 and falls thereafter. The most exposed occupations are
medium-to-high social, not the most social. A variant whose exposure rises monotonically in social
intensity contradicts this.

**Test 2, which social skills (his Tables 2 and 3, and appendix Figure 4).** Combining his component
loadings with his component coefficients gives a predicted sign per social skill:

    Service Orientation   loads +0.25 on component 3, whose DAIOE-LM coefficient is -0.200   -> NEGATIVE
    Social Perceptiveness loads +0.23 on component 3                                          -> NEGATIVE
    Coordination          loads +0.19 on (3), +0.28 on (4), coefficient -0.0732               -> NEGATIVE
    Persuasion            loads +0.23 on (4)                                                  -> NEGATIVE
    Negotiation           loads +0.21 on (4) and -0.29 on (6), coefficient +0.107             -> NEGATIVE
    Instructing           loads -0.23 on (4) and +0.28 on (5)                                 -> POSITIVE

His job-ad clusters agree independently: Service orientation -67.5*, Collaboration -134.2*,
Relationships -44.2**, against Communication +463.3*** and Pedagogical +92.3***.

So of the six O*NET social skills that our mapping matrix scores, Erik's evidence puts five on the
unexposed side and only instructing on the exposed side. Our matrix scores persuasion 0.55,
negotiation 0.45 and service orientation 0.50 for language modeling, which is the opposite.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

MAP = Path(__file__).resolve().parents[1]
OUT = MAP.parent / "data" / "out"
REPORTS = MAP / "reports" / "variants_2024"

SOCIAL_SKILLS = ["socialperceptiveness", "coordination", "persuasion",
                 "negotiation", "instructing", "serviceorientation"]

# Sign each social skill should carry, derived above from Engberg's Tables 2 and 3.
ENGBERG_SIGN = {"serviceorientation": -1, "socialperceptiveness": -1, "coordination": -1,
                "persuasion": -1, "negotiation": -1, "instructing": +1}

# Engberg Table 3, column (1): DAIOE-LM on social intensity and its square.
ENGBERG_HUMP = {"linear": 12.18, "quadratic": -7.575, "peak": 12.18 / (2 * 7.575)}


def _z(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std()


def load_panels() -> dict[str, pd.Series]:
    """Final-year cumulative exposure per panel, plus the published index as a reference."""
    out = {}
    for k in ("R0", "A", "A2", "B"):
        p = pd.read_csv(REPORTS / f"panel_{k}.csv")
        out[k] = p[p.year == p.year.max()].set_index("occ_code_onet").exp_cumul
    pub = pd.read_csv(MAP / "raw_data" / "daioe_onetsoc2010.csv", sep=None, engine="python")
    pub = pub[pub.year == pub.year.max()].set_index("occ_code_onetsoc2010")["daioe_allapps"]
    out["published"] = pub
    return out


def main() -> None:
    panels = load_panels()
    social = pd.read_parquet(OUT / "onet_social_skills_physical_abilities.parquet").set_index("occ_code_onet")
    sk = pd.read_parquet(OUT / "onet_skills_weighted.parquet")
    skill_w = sk[sk.skill.isin(SOCIAL_SKILLS)].pivot_table(
        index="occ_code_onet", columns="skill", values="skill_impact")

    results: dict = {"engberg_reference": {"hump": ENGBERG_HUMP, "signs": ENGBERG_SIGN}, "panels": {}}

    print("TEST 1 — the hump (Engberg Table 3: DAIOE-LM linear 12.18, quadratic -7.575, peak 0.80)\n")
    print(f"  {'panel':<12}{'linear':>10}{'quadratic':>12}{'peak':>8}{'R2':>8}   verdict")
    for name, s in panels.items():
        df = pd.concat([_z(s).rename("y"), social["social_skills"].rename("so")], axis=1).dropna()
        m = smf.ols("y ~ so + I(so**2)", data=df).fit()
        b1, b2 = m.params["so"], m.params["I(so ** 2)"]
        peak = -b1 / (2 * b2) if b2 != 0 else np.nan
        hump = b2 < 0 and 0 < peak < 1.05
        verdict = "hump, consistent" if hump else ("monotone rising" if b2 >= 0 else "peak outside range")
        print(f"  {name:<12}{b1:>10.2f}{b2:>12.2f}{peak:>8.2f}{m.rsquared:>8.3f}   {verdict}")
        results["panels"][name] = {"linear": round(float(b1), 3), "quadratic": round(float(b2), 3),
                                   "peak": round(float(peak), 3), "r2": round(float(m.rsquared), 3),
                                   "hump_consistent": bool(hump)}

    print("\n\nTEST 2 — which social skills go with exposure")
    print("  (partial coefficients, exposure z-scored on the six social-skill weights jointly)\n")
    print(f"  {'social skill':<24}{'Engberg':>9}" + "".join(f"{k:>10}" for k in panels))
    agree = {k: 0 for k in panels}
    for skill in SOCIAL_SKILLS:
        row = f"  {skill:<24}{'+' if ENGBERG_SIGN[skill] > 0 else '-':>9}"
        for k, s in panels.items():
            df = pd.concat([_z(s).rename("y"), skill_w], axis=1).dropna()
            m = smf.ols("y ~ " + " + ".join(SOCIAL_SKILLS), data=df).fit()
            b = m.params[skill]
            sig = "*" if m.pvalues[skill] < 0.05 else " "
            row += f"{b:>9.2f}{sig}"
            if np.sign(b) == ENGBERG_SIGN[skill]:
                agree[k] += 1
            results["panels"].setdefault(k, {}).setdefault("skill_signs", {})[skill] = round(float(b), 3)
        print(row)
    print(f"\n  {'signs matching Engberg':<24}{'6/6':>9}" + "".join(f"{agree[k]}/6".rjust(10) for k in panels))
    for k in panels:
        results["panels"][k]["engberg_sign_agreement"] = f"{agree[k]}/6"

    (REPORTS / "engberg_test.json").write_text(json.dumps(results, indent=2))
    print(f"\nwrote {REPORTS / 'engberg_test.json'}")


if __name__ == "__main__":
    main()
