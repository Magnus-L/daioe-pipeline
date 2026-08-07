"""
compare_constructions.py — the deciding run for the task-level DAIOE.

Everything here was fixed in `notes/DESIGN-task-level-daioe_2026-08-07.md` BEFORE the deciding
batch was submitted: the candidates, the benchmarks, the derived parameter, and the adoption rule.
This script only executes that design.

Candidates (none touches the published index):

    C0  52 abilities, relatedness, no discount            the current best
    C1  C0 + 17 social activities by threshold            the hybrid that fixed the ordering
    C2  all 41 activities by threshold                    the task-level model, fully derived
    C3  52 abilities, relatedness, delta=2 discount       the published-equivalent

Benchmarks:

    B1  Eloundou human_E1 / E1+E2, like-for-like on the language-modelling sub-index (task-RATED)
    B2  face-validity ordering, monotone: telemarketers > customer service > clergy >
        mental-health counsellors > clinical psychologists
    B3  AEI usage by occupation (task-REVEALED; the benchmark neither we nor Eloundou tuned to),
        against the allapps index because usage reflects all applications of the deployed system
    B4  the proxy demonstration (reported, not gated)

Adoption rule: recommend replacing the discount only if C1 or C2 is within 0.02 of C0 on B1,
passes B2 monotonically, and on B3 reaches 0.6 and is no worse than C0. If C2 passes it wins,
being the derived construction.

k = 3.70 is DERIVED (sigma from O*NET standard errors and replicate dispersion); k in {2, 4} is
reported as robustness around it, never used for selection.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

MAP = Path(__file__).resolve().parents[1]
ROOT = MAP.parent
REPORTS = MAP / "reports" / "threshold_track"

K_DERIVED = 3.70
FACE = ["Telemarketers", "Customer Service Representatives", "Clergy",
        "Mental Health Counselors", "Clinical Psychologists"]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, MAP / "code" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


bv, tw, tp = _load("build_2024_variants"), _load("threshold_weights"), _load("threshold_panel")


def relatedness_matrix(elements: pd.DataFrame) -> pd.DataFrame:
    m = pd.concat([pd.read_csv(MAP / "output" / "mapping_matrix_claude_v2026.csv", index_col=0),
                   pd.read_csv(MAP / "output" / "mapping_matrix_claude_vconv.csv", index_col=0)]).sort_index()
    m.columns = [int(c) for c in m.columns]
    return m.rename(columns=dict(zip(elements.ability_id, elements.element_id)))


def build_candidates(elements, apps) -> dict[str, dict[float, pd.DataFrame]]:
    """A(o,i) per candidate per steepness. C0 and C3 have no threshold, keyed at k=None."""
    M = relatedness_matrix(elements)
    req_a, w_a = tw.load(["ability"], elements)
    acols = [c for c in M.columns if c in w_a.columns]
    A0 = pd.DataFrame({i: (w_a[acols].values * M.loc[i, acols].values[None, :]).sum(1)
                       for i in M.index}, index=w_a.index)

    out: dict[str, dict] = {"C0": {None: A0}, "C1": {}, "C2": {}}
    for k in (2.0, K_DERIVED, 4.0):
        # C1: abilities by relatedness + the 17 social activities by threshold
        req_s, w_s = tw.load(["activity"], elements)
        att_s = tp.load_attained(["activity"], elements)
        scols = [c for c in att_s.columns if c in req_s.columns]
        occ = A0.index.intersection(req_s.index)
        thr = {}
        for i in att_s.index:
            g = 1 / (1 + np.exp(-k * (att_s.loc[i, scols].values[None, :] - req_s.loc[occ, scols].values)))
            thr[i] = (w_s.loc[occ, scols].values * g).sum(1)
        out["C1"][k] = A0.loc[occ] + pd.DataFrame(thr, index=occ)

        # C2: the full 41-activity task-level model
        req_t, w_t = tw.load(["activity", "activity_nonsocial"], elements)
        att_t = tp.load_attained(["activity", "activity_nonsocial"], elements)
        tcols = [c for c in att_t.columns if c in req_t.columns]
        thr2 = {}
        for i in att_t.index:
            g = 1 / (1 + np.exp(-k * (att_t.loc[i, tcols].values[None, :] - req_t[tcols].values)))
            thr2[i] = (w_t[tcols].values * g).sum(1)
        out["C2"][k] = pd.DataFrame(thr2, index=req_t.index)

    # C3: published-equivalent discount on C0
    soc = pd.read_parquet(ROOT / "data" / "out" / "onet_social_skills_physical_abilities.parquet")
    temp = (1.0 - soc["social_skills"]) + 2.0
    score = pd.Series((temp / temp.max()).values, index=soc["occ_code_onet"])
    out["C3"] = {None: A0.mul(score.reindex(A0.index), axis=0)}
    return out


def main() -> None:
    elements = pd.read_csv(MAP / "raw_data" / "abilities_v2.csv")
    apps = pd.read_csv(MAP / "raw_data" / "applications_v2.csv")
    names = dict(zip(apps.ai_app_id, apps.frs_row.str.strip().str.lower()))
    progress = bv.load_progress()
    lm = progress[progress.application == "language modeling"]
    el = pd.read_stata(ROOT / "data" / "raw" / "openai_2024_exposure_soc2010.dta").set_index("occ_code_soc2010")
    aei = pd.read_csv(MAP / "raw_data" / "aei" / "aei_usage_by_occupation.csv").set_index("occ_code_onet").aei_usage
    titles = (pd.read_parquet(ROOT / "data" / "out" / "onet_abilities_weighted.parquet")
              .drop_duplicates("occ_code_onet").set_index("occ_code_onet")["Title"])

    cands = build_candidates(elements, apps)
    rows, face_rows = [], {}
    for cname, byk in cands.items():
        for k, A in byk.items():
            # B1: Eloundou, LM sub-index
            p = tp.build(A, lm, names)
            p = p[p.year == p.year.max()].copy()
            p["soc"] = p.occ_code_onet.str[:7]
            j = pd.concat([p.groupby("soc").exp_cumul.mean().rename("o"),
                           el[["human_E1", "human_E1_E2"]]], axis=1).dropna()
            e1 = spearmanr(j.o, j.human_E1).statistic
            e2 = spearmanr(j.o, j.human_E1_E2).statistic

            # allapps panel for B2 and B3
            q = tp.build(A, progress, names)
            f = q[q.year == q.year.max()].set_index("occ_code_onet").exp_cumul
            pct = f.rank(pct=True)
            vals = [float(pct.reindex([c for c in titles.index if str(titles[c]).strip() == n]).mean())
                    for n in FACE]
            mono = all(a >= b for a, b in zip(vals, vals[1:]))

            # B3: AEI usage — both on matched occupations and with zeros for the unobserved
            ja = pd.concat([f.rename("o"), aei], axis=1)
            r_obs = spearmanr(ja.dropna().o, ja.dropna().aei_usage).statistic
            ja0 = ja.copy()
            ja0["aei_usage"] = ja0.aei_usage.fillna(0.0)
            r_all = spearmanr(ja0.dropna(subset=["o"]).o, ja0.dropna(subset=["o"]).aei_usage).statistic

            key = f"{cname}" + (f" k={k:g}" if k is not None else "")
            face_rows[key] = vals
            rows.append({"candidate": cname, "k": k, "E1": round(float(e1), 4),
                         "E1E2": round(float(e2), 4), "aei_obs": round(float(r_obs), 4),
                         "aei_all": round(float(r_all), 4), "face_monotone": mono,
                         "face": [round(v, 2) for v in vals]})

    tab = pd.DataFrame(rows)
    print("THE DECIDING RUN  (design and rule pre-committed in DESIGN-task-level-daioe)\n")
    print(tab.drop(columns="face").to_string(index=False))
    print("\nface-validity percentiles (telemarketers, cust.service, clergy, counsellors, psychologists):")
    for kk, v in face_rows.items():
        print(f"  {kk:<12} " + "  ".join(f"{x:.2f}" for x in v))

    # the adoption rule, mechanically
    c0 = tab[(tab.candidate == "C0")].iloc[0]
    verdicts = {}
    for cname in ("C1", "C2"):
        sub = tab[(tab.candidate == cname) & (tab.k == K_DERIVED)]
        if sub.empty:
            continue
        r = sub.iloc[0]
        checks = {"B1 within 0.02 of C0": bool(r.E1 >= c0.E1 - 0.02),
                  "B2 monotone": bool(r.face_monotone),
                  "B3 >= 0.6 and >= C0": bool(r.aei_obs >= 0.6 and r.aei_obs >= c0.aei_obs - 1e-9)}
        verdicts[cname] = checks
        print(f"\n{cname} at derived k={K_DERIVED}: " +
              "; ".join(f"{k}: {'PASS' if v else 'FAIL'}" for k, v in checks.items()))

    rec = ("C2" if all(verdicts.get("C2", {}).values()) and verdicts.get("C2") else
           "C1" if all(verdicts.get("C1", {}).values()) and verdicts.get("C1") else
           "keep the discount; neither candidate passes")
    print(f"\nRECOMMENDATION UNDER THE PRE-STATED RULE: {rec}")

    (REPORTS / "deciding_run.json").write_text(json.dumps(
        {"k_derived": K_DERIVED, "results": rows, "verdicts": verdicts,
         "recommendation": rec}, indent=2, default=str))
    print(f"\nwrote {REPORTS / 'deciding_run.json'}")


if __name__ == "__main__":
    main()
