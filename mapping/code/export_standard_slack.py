"""
export_standard_slack.py — the standard-slack auxiliary variable, packaged for the extensions paper.

Correction of framing (Magnus, 7 Aug evening): DAIOE is agnostic about channels; distinguishing
automation from augmentation is the extensions paper's mission, and that paper takes DAIOE as an
input. The attained-versus-required construction is therefore NOT a second DAIOE and NOT a channel
label. What it measures is **standard-slack**:

    slack(i, j)    = attained(i, j) − required(o, j)          per application, element, occupation
    SLACK(o, i)    = Σ_j w(o,j) · Φ( slack / σ )              share of o's work where application i
                                                              meets the occupation's standard
    SLACK(o)       = max_i SLACK(o, i)                        the frontier version

Slack is channel-agnostic. AI below an occupation's standard can still augment its workers; AI
above it can automate or augment, and deployment decides. What slack offers the extensions paper is
*identifying variation*: where DAIOE exposure is high and slack is low, exposure can only be
augmentation-shaped; where both are high, automation is feasible and the outcome is informative
about deployment. That interaction is the extensions paper's to exploit; nothing here asserts a
channel.

Validation already on file (`RESULT-two-margin-daioe_2026-08-07.md`, reread under this framing):
SLACK correlates +0.60 with Frey-Osborne's computerisation probability (a feasibility-flavoured
measure), while DAIOE-applicability correlates +0.76 with Eloundou and +0.56 with AEI usage — each
object tracks its own kind of external evidence, which is what distinct inputs should do.

Outputs (all under mapping/reports/threshold_track/export/):
    slack_occupation.csv            SLACK(o) + per-application columns, O*NET-SOC 2010
    slack_occupation_element.csv    the full (o, j) required/attained/slack detail, long form
    slack_readme.md                 provenance, construction, and the k derivation
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

MAP = Path(__file__).resolve().parents[1]
EXPORT = MAP / "reports" / "threshold_track" / "export"
EXPORT.mkdir(parents=True, exist_ok=True)

K = 3.70   # 1.702 / sqrt(SE_onet^2 + sd_replicates^2); see the readme this script writes


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, MAP / "code" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    tw, tp = _load("threshold_weights"), _load("threshold_panel")
    elements = pd.read_csv(MAP / "raw_data" / "abilities_v2.csv")
    apps = pd.read_csv(MAP / "raw_data" / "applications_v2.csv")
    app_name = dict(zip(apps.ai_app_id, apps.name))

    blocks = ["activity", "activity_nonsocial"]
    required, weight = tw.load(blocks, elements)
    attained = tp.load_attained(blocks, elements)
    cols = [c for c in attained.columns if c in required.columns]
    ename = dict(zip(elements.element_id, elements.ability_name))

    # occupation x application SLACK
    slack_oa = {}
    long_rows = []
    for i in attained.index:
        gap = attained.loc[i, cols].values[None, :] - required[cols].values
        g = 1.0 / (1.0 + np.exp(-K * gap))
        slack_oa[i] = (weight[cols].values * g).sum(axis=1)
        d = pd.DataFrame({
            "occ_code_onet": np.repeat(required.index.values, len(cols)),
            "element_id": np.tile(cols, len(required)),
            "required_level": required[cols].values.ravel(),
            "attained_level": np.tile(attained.loc[i, cols].values, len(required)),
        })
        d["slack"] = d.attained_level - d.required_level
        d["application"] = app_name[i]
        long_rows.append(d)

    SA = pd.DataFrame(slack_oa, index=required.index)
    out = pd.DataFrame({"slack_frontier": SA.max(axis=1)})
    for i in SA.columns:
        out[f"slack_{app_name[i].lower().replace(' ', '_')}"] = SA[i]
    out.index.name = "occ_code_onet"
    out.round(4).to_csv(EXPORT / "slack_occupation.csv")

    long = pd.concat(long_rows, ignore_index=True)
    long["element_name"] = long.element_id.map(ename)
    long.round(3).to_csv(EXPORT / "slack_occupation_element.csv", index=False)

    (EXPORT / "slack_readme.md").write_text(f"""# Standard-slack auxiliary variable, v1 ({date.today().isoformat()})

Companion data for the DAIOE extensions paper. **Not part of DAIOE**, which remains agnostic about
channels; slack is identifying variation for the extensions paper's channel analysis.

## Construction
For each of O*NET's 41 generalised work activities (database 22.2), an AI application's *attained
level* was scored against O*NET's published level anchors (three replicates, Claude Opus 5,
median replicate spread 0.20 of a level). *Required level* and importance-based weights are O*NET's
own occupation data on the identical scales. SLACK(o,i) = importance-weighted share of occupation
o's activities where application i's attained level clears o's required level, smoothed by a
logistic with k = 1.702/sigma = {K}, sigma = sqrt(0.447^2 + 0.111^2) from O*NET's published
standard errors and the replicate dispersion. Nothing is hand-set.

## Interpretation discipline
Slack says whether AI meets the occupation's standard on its activities. It does NOT say whether
deployment automates or augments; that inference is the analysis's job, e.g. via the interaction of
DAIOE exposure with slack. AI below standard can augment; AI above standard can do either.

## External behaviour
Occupation-level frontier slack correlates +0.60 (Spearman, n=685) with Frey & Osborne (2017)
p(computerisation); DAIOE-applicability instead tracks Eloundou et al. human ratings (+0.76) and
Anthropic Economic Index usage (+0.56). Distinct objects, each tracking its own kind of evidence.

## Files
- slack_occupation.csv: SLACK(o) frontier + one column per application (O*NET-SOC 2010, n=966)
- slack_occupation_element.csv: full (occupation, activity, application) detail with required,
  attained and raw slack
""")
    print(f"wrote {EXPORT}/slack_occupation.csv        ({len(out)} occupations)")
    print(f"wrote {EXPORT}/slack_occupation_element.csv ({len(long):,} rows)")
    print(f"wrote {EXPORT}/slack_readme.md")


if __name__ == "__main__":
    main()
