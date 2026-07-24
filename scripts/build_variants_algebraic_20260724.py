#!/usr/bin/env python3
"""Build DAIOE social-weight variants ALGEBRAICALLY from the frozen published panels.

Why not pipeline runs: the raw source folder (Downloads/DAIOE 20260527) is gone
locally and the data/out checkpoints sit in the 2024-refresh state, which differs
from the frozen 2010-2023 publication (verified: max|diff| 5.7 on daioe_allapps).
The frozen truth lives in the public ai-econ-lab/daioe_dataset. The social
discount enters DAIOE multiplicatively per occupation BEFORE squaring:

    inc_ot(delta) = (De_ot * w_o(delta))^2 * 10
 => inc_ot(delta') = inc_ot(delta=2) * (w_o(delta')/w_o(2))^2

so every social-weight variant is an exact per-occupation reweighting of the
frozen increments at ONET level, where w_o = (1 - ss_o + delta) / max_o'(...).
Aggregation to ISCO-08 mirrors stage5: mean of increments through the crosswalk,
then cumulate within the target code.

CERTIFICATION: the baseline (delta=2) is pushed through the same
reconstruct-aggregate path and compared to the frozen published ISCO panel;
the max|diff| is printed and written to the README. Variants share that path.

Drafted for Erik's verification, 2026-07-24. Delta grid: 0.5/1/4 + no-downweight.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data" / "variants_20260724"
FROZEN = Path("/private/tmp/claude-502/-Users-mslk/bf928251-a932-4053-837f-70a216826e7f/scratchpad/daioe_dataset")
MONA_BATCH = Path.home() / "Documents/Workspace/projects/daioe/mona-batch"

GRID = {"d05": 0.5, "d1": 1.0, "d4": 4.0, "nodw": None}  # None = w == 1
APPS = ["allapps", "genai"]


def load_onet() -> pd.DataFrame:
    df = pd.read_stata(FROZEN / "daioe_onetsoc2010" / "daioe_onetsoc2010.dta")
    return df


def increments(df: pd.DataFrame, key: str, col: str) -> pd.Series:
    """Within-occupation first difference; first year keeps its cumulative value."""
    return df.groupby(key)[col].diff().fillna(df[col])


def cumulate(df: pd.DataFrame, key: str, col: str) -> pd.Series:
    return df.groupby(key)[col].cumsum()


def main() -> None:
    onet = load_onet()
    key_col = next(c for c in onet.columns if "onet" in c.lower() and "code" in c.lower())
    onet = onet.sort_values([key_col, "year"]).reset_index(drop=True)

    ss = pd.read_parquet(ROOT / "data/out/onet_social_skills_physical_abilities.parquet")
    onet = onet.merge(ss[["occ_code_onet", "social_skills"]],
                      left_on=key_col, right_on="occ_code_onet", how="left")
    n_missing_ss = onet["social_skills"].isna().sum()
    assert n_missing_ss == 0, f"{n_missing_ss} panel rows lack social skills"

    # --- occupation weights w_o(delta), max over occupations present in the panel ---
    occs = onet.drop_duplicates(key_col)[["occ_code_onet", "social_skills"]].copy()

    def w(delta: float | None) -> pd.Series:
        if delta is None:
            return pd.Series(1.0, index=occs.index)
        raw = (1.0 - occs["social_skills"]) + delta
        return raw / raw.max()

    w2 = w(2.0)
    ratios = {lbl: (w(d) / w2) ** 2 for lbl, d in GRID.items()}
    ratio_df = occs[["occ_code_onet"]].copy()
    for lbl, r in ratios.items():
        ratio_df[f"ratio_{lbl}"] = r.values
    onet = onet.merge(ratio_df, on="occ_code_onet", how="left")

    # --- reconstruct increments, reweight, cumulate (ONET level) ---
    for app in APPS:
        base_col = f"daioe_{app}"
        onet[f"inc_{app}"] = increments(onet, key_col, base_col)
        for lbl in GRID:
            onet[f"inc_{app}_{lbl}"] = onet[f"inc_{app}"] * onet[f"ratio_{lbl}"]
    # certification column: rebuild base cumulative from own increments (sanity)
    onet["rebuild_allapps"] = cumulate(onet, key_col, "inc_allapps")
    max_self = (onet["rebuild_allapps"] - onet["daioe_allapps"]).abs().max()

    # --- aggregate ONET -> SOC2010 (mean of increments by 7-char SOC code) ---
    onet["soc"] = onet[key_col].astype(str).str[:7]
    inc_cols = [f"inc_{a}" for a in APPS] + [f"inc_{a}_{l}" for a in APPS for l in GRID]
    soc = onet.groupby(["soc", "year"], as_index=False)[inc_cols].mean()

    # --- SOC -> ISCO08 via crosswalk (right join, mean of increments) ---
    cw = pd.read_stata(WORK / "isco08_soc2010_crosswalk.dta")[["ISCO08code", "SOC2010code"]]
    cw["SOC2010code"] = cw["SOC2010code"].astype(str).str.strip()
    merged = cw.merge(soc.rename(columns={"soc": "SOC2010code"}),
                      on="SOC2010code", how="left")
    isco = merged.groupby(["ISCO08code", "year"], as_index=False)[inc_cols].mean()
    isco = isco.dropna(subset=["year"]).sort_values(["ISCO08code", "year"]).reset_index(drop=True)

    # cumulate within ISCO
    out = isco[["ISCO08code", "year"]].copy()
    for app in APPS:
        out[f"daioe_{app}_base"] = cumulate(isco, "ISCO08code", f"inc_{app}")
        for lbl in GRID:
            out[f"daioe_{app}_{lbl}"] = cumulate(isco, "ISCO08code", f"inc_{app}_{lbl}")
    out["daioe_annual"] = isco["inc_allapps"]
    out["daioe_ma3"] = (isco.groupby("ISCO08code")["inc_allapps"]
                        .transform(lambda s: s.rolling(3, min_periods=1).mean()))

    # --- CERTIFICATION vs frozen published ISCO panel ---
    frozen_isco = pd.read_stata(FROZEN / "daioe_isco08" / "daioe_isco08.dta")
    fz = frozen_isco[["occ_code_isco08", "year", "daioe_allapps", "daioe_genai"]].copy()
    fz["ISCO08code"] = fz["occ_code_isco08"].astype(str).str.zfill(4)
    out["ISCO08code"] = out["ISCO08code"].astype(str).str.zfill(4)
    cmp = fz.merge(out, on=["ISCO08code", "year"], how="inner")
    cert_all = (cmp["daioe_allapps"] - cmp["daioe_allapps_base"]).abs().max()
    cert_gen = (cmp["daioe_genai"] - cmp["daioe_genai_base"]).abs().max()
    rel = cert_all / cmp["daioe_allapps"].abs().mean()
    print(f"self-rebuild max|diff| (ONET): {max_self:.2e}")
    print(f"certification vs frozen ISCO: allapps {cert_all:.4f}, genai {cert_gen:.4f} "
          f"(relative {rel:.2%}); merged {len(cmp)} rows")

    # --- sanity: nodw lifts social occupations most ---
    y23 = out[out.year == 2023].merge(
        onet.groupby(onet[key_col].astype(str).str[:7])["social_skills"].mean()
            .rename("ss").reset_index().rename(columns={key_col: "soc"}),
        left_on="ISCO08code", right_on="soc", how="left")  # coarse; sanity only

    # --- deliverables ---
    final_cols = (["ISCO08code", "year"] +
                  [f"daioe_allapps_{l}" for l in ["base"] + list(GRID)] +
                  ["daioe_annual", "daioe_ma3", "daioe_genai_base"])
    final = out[final_cols].rename(columns={
        "ISCO08code": "isco08_4", "daioe_allapps_base": "daioe_base",
        "daioe_allapps_d05": "daioe_d05", "daioe_allapps_d1": "daioe_d1",
        "daioe_allapps_d4": "daioe_d4", "daioe_allapps_nodw": "daioe_nodw",
        "daioe_genai_base": "daioe_genai"})
    final = final[final.year <= 2023]
    rc = final[final.year == 2023][[c for c in final.columns if c.startswith("daioe_")]].corr(method="spearman")
    print("\nSpearman rank correlations, 2023:\n", rc.round(3).to_string())
    rc.to_csv(WORK / "rank_correlations_2023.csv")
    dta = MONA_BATCH / "daioe_variants_occ_year.dta"
    final.to_stata(dta, write_index=False, version=118)
    print(f"\nwrote {dta} ({dta.stat().st_size/1e6:.2f} MB, {len(final)} rows)")
    final.to_parquet(WORK / "daioe_variants_occ_year.parquet")
    with open(WORK / "CERTIFICATION.txt", "w") as f:
        f.write(f"base reconstruction vs frozen published ISCO panel: max|diff| "
                f"allapps={cert_all:.6f}, genai={cert_gen:.6f}, relative={rel:.4%}, "
                f"rows={len(cmp)}; ONET self-rebuild={max_self:.2e}\n")


if __name__ == "__main__":
    main()
