"""Wire the v1.1.0 release candidate: G2 + the two activated columns through the
five-taxonomy exports, on top of the admitted vintage, under the strengthened gates.

Decisions executed (all 24 Aug 2026, Lodefalk & Engberg): D9 makes the
second-generation composite part of the ORIGINAL 2025 vintage; D1b activates the
agentic and maths/science exposure columns from the approved FRS 2018 rows
(Claude-certified, ChatGPT-confirmed). This script carries all three occupation-level
series (computed by build_g2_composite_20260824.py and build_activation_20260824.py at
O*NET level) into every taxonomy of the release, reusing stage 5's own primitives so
the fan-out arithmetic is the pipeline's, not a reimplementation:

  ONET -> SOC       unweighted mean of exp_change by (occ_code_soc, year), then
                    cumulate within SOC (stage5._cumul_within)
  SOC  -> targets   per-year right-merge with the same crosswalk .dta files, unweighted
                    mean by (target, year), cumulate, exact-zero cumulative -> missing
                    (the do-file's own rule)

Column conventions: internal panels gain exp_change_/exp_cumul_ for g2all, agentic,
mathsci; Publication panels gain daioe_g2all/daioe_agentic/daioe_mathsci (the
cumulative) and pctl_rank_ for each (so.pctl_rank, within year). Entry discipline:
agentic and mathsci are NaN before 2024 and zero at their 2024 chain year, exactly like
conversation and software; G2 spans the full window BY DESIGN (D9: the second
generation has a complete history of its own; it is a new column, so nothing frozen
can move).

Gates: the assembler's strengthened gate_publication_seam and gate_internal_seam are
re-run on the wired folder (frozen columns byte-identical, PL-M2 completeness), plus
this script's own checks: chained-column silence before 2024, row counts unchanged,
and G2 present in every taxonomy.

Output: data/vintage/vintage_2025_v110rc_20260824/ (out/ + Publication/) and
reports/vintage_2025_v110rc_20260824/RELEASE-v110rc.md.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daioe import io as dio  # noqa: E402
from daioe import stata_ops as so  # noqa: E402
from daioe.stage5_taxonomies import _cumul_within  # noqa: E402

SRC = ROOT / "data/vintage/vintage_2025_admitted_20260824"
G2DIR = ROOT / "data/vintage/g2_20260824"
DST = ROOT / "data/vintage/vintage_2025_v110rc_20260824"
REP = ROOT / "reports/vintage_2025_v110rc_20260824"
NEW = ["g2all", "agentic", "mathsci"]
YEARS = list(range(2010, 2026))

# ------------------------------------------------------------------ copy base --
if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(SRC, DST)
REP.mkdir(parents=True, exist_ok=True)
OUT = DST / "out"
print(f"base copied: {SRC.name} -> {DST.name}")

# ---------------------------------------------- the three ONET change columns --
g2 = pd.read_parquet(G2DIR / "g2_panel_onet.parquet")[["occ_code_onet", "year", "g2_change"]]
g2 = g2.rename(columns={"g2_change": "exp_change_g2all"})
def activated(tag):
    p = pd.read_parquet(G2DIR / f"activated_{tag}_panel_onet.parquet")
    p = p[["occ_code_onet", "year", "exp_change"]].rename(
        columns={"exp_change": f"exp_change_{tag}"})
    base = p[["occ_code_onet"]].drop_duplicates().assign(year=2024.0)
    base[f"exp_change_{tag}"] = 0.0            # chain-year baseline, like conversat/software
    return pd.concat([base, p], ignore_index=True)

onet_new = g2.merge(activated("agentic"), on=["occ_code_onet", "year"], how="outer")
onet_new = onet_new.merge(activated("mathsci"), on=["occ_code_onet", "year"], how="outer")

# ---------------------------------------------------------------- fan-out ----
prelim = pd.read_parquet(OUT / "daioe_panel_onet_preliminary.parquet")
onet_soc = prelim[["occ_code_onet", "occ_code_soc"]].drop_duplicates()
onet_soc["occ_code_soc"] = onet_soc["occ_code_soc"].replace("19-1020", "19-1029")

def cumulate(df, key):
    for a in NEW:
        df[f"exp_change_{a}"] = so.f32(df[f"exp_change_{a}"])
        col = f"exp_cumul_{a}"
        df[col] = _cumul_within(df, key, f"exp_change_{a}")
        # the running-sum primitive follows Stata in treating missing as zero,
        # which would print 0.0 before a chained series' entry year; the declared
        # silence rule (G3) says NaN there, matching conversation and software.
        if a in ("agentic", "mathsci"):
            vals = np.array(df[col].to_numpy(dtype=np.float64), copy=True)
            vals[df["year"].to_numpy(dtype=float) < 2024] = np.nan
            df[col] = vals
        df[col] = so.f32(df[col])
    return df

# ONET level: cumulate within occupation
onet_cols = onet_new.sort_values(["occ_code_onet", "year"], kind="mergesort").reset_index(drop=True)
onet_cols = cumulate(onet_cols, "occ_code_onet")

# SOC level: unweighted mean by (occ_code_soc, year), then cumulate
soc_in = onet_new.merge(onet_soc, on="occ_code_onet", how="left").dropna(subset=["occ_code_soc"])
soc_cols = (soc_in.groupby(["occ_code_soc", "year"], as_index=False)
            [[f"exp_change_{a}" for a in NEW]].mean())
soc_cols = soc_cols.sort_values(["occ_code_soc", "year"], kind="mergesort").reset_index(drop=True)
soc_cols = cumulate(soc_cols, "occ_code_soc")

def crosswalk_cols(cw_file, target_key, zero_to_nan=True):
    p = ROOT / "data/raw" / cw_file
    if not p.exists():
        p = ROOT / "data/derived" / cw_file
    cw = dio.read_dta(str(p))[["SOC2010code", target_key]].dropna()
    pieces = []
    for y in YEARS:
        sub = soc_cols[soc_cols.year == y].rename(columns={"occ_code_soc": "SOC2010code"})
        m = sub.merge(cw, on="SOC2010code", how="right")
        m["year"] = float(y)
        pieces.append(m.groupby([target_key, "year"], as_index=False)
                      [[f"exp_change_{a}" for a in NEW]].mean())
    out = (pd.concat(pieces, ignore_index=True)
           .sort_values([target_key, "year"], kind="mergesort").reset_index(drop=True))
    for a in NEW:
        out[f"exp_change_{a}"] = so.f32(out[f"exp_change_{a}"])
        col = f"exp_cumul_{a}"
        out[col] = _cumul_within(out, target_key, f"exp_change_{a}")
        if a in ("agentic", "mathsci"):
            vals = np.array(out[col].to_numpy(dtype=np.float64), copy=True)
            vals[out["year"].to_numpy(dtype=float) < 2024] = np.nan
            out[col] = vals
        if zero_to_nan:
            vals = np.array(out[col].to_numpy(dtype=np.float64), copy=True)
            vals[vals == 0.0] = np.nan
            out[col] = so.f32(vals)
        else:
            out[col] = so.f32(out[col])
    return out

targets = {
    "daioe_panel_isco08.dta":  ("isco08_soc2010_crosswalk.dta", "ISCO08code", "ISCO08code_str"),
    "daioe_panel_ssyk2012.dta": ("ssyk2012_soc10_crosswalk.dta", "ssyk2012_4", "ssyk2012_4"),
    "daioe_panel_ssyk96.dta":  ("ssyk96_soc10_crosswalk.dta", "SSYK96kod", "ssyk96_4"),
    "daioe_panel_soc2018.dta": ("soc2010_to_soc2018_BLS.dta", "SOC2018code", "SOC2018code"),
}

# --------------------------------------------------- append to internal panels --
def append_internal(fname, newframe, key_in_new, key_in_panel):
    panel = dio.read_dta(OUT / fname)
    nf = newframe.rename(columns={key_in_new: key_in_panel})
    nf = nf[[key_in_panel, "year"] + [c for c in nf.columns if c.startswith("exp_")]]
    before = len(panel)
    kl = panel[key_in_panel].astype(str)
    nf[key_in_panel] = nf[key_in_panel].astype(str)
    panel["_k"] = kl
    nf = nf.rename(columns={key_in_panel: "_k"})
    merged = panel.merge(nf, on=["_k", "year"], how="left").drop(columns="_k")
    assert len(merged) == before, f"{fname}: row count changed in wiring"
    dio.write_dta(merged, OUT / fname)
    return merged

wired = {}
wired["onet"] = append_internal("daioe_panel_onet.dta", onet_cols, "occ_code_onet", "occ_code_onet")
wired["soc"] = append_internal("daioe_panel_soc.dta", soc_cols, "occ_code_soc", "occ_code_soc")
for fname, (cw, tkey, panel_key) in targets.items():
    frame = crosswalk_cols(cw, tkey)
    if fname == "daioe_panel_ssyk96.dta":
        # the SSYK96 crosswalk stores zero-padded string codes ("0110") while the
        # panel stores numerics (110.0); build_ssyk96 makes the same conversion
        frame[tkey] = pd.to_numeric(frame[tkey], errors="coerce").astype(float)
    wired[fname] = append_internal(fname, frame, tkey, panel_key)
print("internal panels wired: onet, soc + 4 crosswalk taxonomies")

# ------------------------------------------------- append to Publication panels --
PUB = OUT / "Publication"
pub_keys = {
    "daioe_onetsoc2010": ("occ_code_onetsoc2010", "onet", "occ_code_onet"),
    "daioe_soc2010":     ("occ_code_soc2010", "soc", "occ_code_soc"),
    "daioe_isco08":      ("occ_code_isco08", "daioe_panel_isco08.dta", "ISCO08code_str"),
    "daioe_ssyk2012":    ("ssyk2012_4", "daioe_panel_ssyk2012.dta", "ssyk2012_4"),
    "daioe_ssyk96":      ("ssyk96_4", "daioe_panel_ssyk96.dta", "ssyk96_4"),
}
for stem, (pkey, src_key, src_col) in pub_keys.items():
    pub = dio.read_dta(PUB / f"{stem}.dta")
    srcp = wired[src_key]
    add = srcp[[src_col, "year"] + [f"exp_cumul_{a}" for a in NEW]].copy()
    add.columns = [pkey, "year"] + [f"daioe_{a}" for a in NEW]
    add[pkey] = add[pkey].astype(str)
    pub["_k"] = pub[pkey].astype(str)
    add = add.rename(columns={pkey: "_k"})
    before = len(pub)
    pub = pub.merge(add, on=["_k", "year"], how="left").drop(columns="_k")
    assert len(pub) == before, f"{stem}: row count changed"
    for a in NEW:
        pub[f"pctl_rank_{a}"] = so.f32(
            so.pctl_rank(pub, value=f"daioe_{a}", out=f"pctl_rank_{a}"))
    dio.write_dta(pub, PUB / f"{stem}.dta")
    dio.write_csv_tab(pub, PUB / f"{stem}.csv")
    dio.write_xlsx(pub, PUB / f"{stem}.xlsx")
print("Publication panels wired: 5 taxonomies x 3 formats")

# --------------------------------------------------------------------- gates ---
aspec = importlib.util.spec_from_file_location(
    "asm", ROOT / "scripts/assemble_vintage_2025_20260808.py")
asm = importlib.util.module_from_spec(aspec)
aspec.loader.exec_module(asm)
lines = asm.gate_publication_seam(PUB)
lines += ["internal " + l for l in asm.gate_internal_seam(OUT)]
for l in lines:
    print("      " + l)

# own checks: chained silence + G2 presence
for stem, (pkey, _, _) in pub_keys.items():
    pub = dio.read_dta(PUB / f"{stem}.dta")
    for a in ("agentic", "mathsci"):
        pre = pub[(pub.year < 2024)][f"daioe_{a}"]
        assert pre.isna().all(), f"{stem}: daioe_{a} not silent before 2024"
    assert pub["daioe_g2all"].notna().sum() > 0, f"{stem}: G2 missing"
print("      chained-column silence + G2 presence: PASSED in all five taxonomies")

(REP / "RELEASE-v110rc.md").write_text(
    "# v1.1.0 release candidate (wired 24 Aug 2026)\n\n"
    "Base: vintage_2025_admitted_20260824 (metr80 primary agentic + OSWorld, GDPval; "
    "MATH Level 5; SimpleBench; TAC95 staged for corroboration).\n"
    "Added columns, all taxonomies: daioe_g2all (the D9 second-generation composite, "
    "full window 2010-2025), daioe_agentic and daioe_mathsci (D1b activation, FRS 2018 "
    "rows, chained 2024), each with pctl_rank_. Fan-out via stage 5's own primitives; "
    "sigma table data/derived/g2_sigma_v1.csv; G2 checks in reports/g2_20260824.\n\n"
    "## Gates\n" + "\n".join(f"- {l}" for l in lines) +
    "\n- chained-column silence (agentic, mathsci pre-2024) and G2 presence: PASSED\n")
print(f"\nwrote {REP.relative_to(ROOT)}/RELEASE-v110rc.md")
