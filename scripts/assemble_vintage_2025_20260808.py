"""Assemble the 2025 DAIOE vintage: one documented chain point (Track B B5).

The release object under the settled seam policy (checkpoint2, decision 2026-07-07):
published 2010-2023 values IMMUTABLE, 2024-2025 increments computed on the fuller
archive and chained on at 2023. Every Erik decision of 15 August is a command-line
flip, so the meeting changes flags, not code.

    python scripts/assemble_vintage_2025_20260808.py                # default build
    python scripts/assemble_vintage_2025_20260808.py --gpqa-parent qa
    python scripts/assemble_vintage_2025_20260808.py --allapps-rule mean
    python scripts/assemble_vintage_2025_20260808.py --membership plus-new

Inputs (all admitted through the guarded doors; none revises a published value):
  benchmark_updates    measures_updates_2024plus.xlsx (Track A, PwC archive)
                       measures_updates_epoch_2026-08-07.xlsx (Epoch refresh, 5 series)
  benchmark_extensions GPQA Diamond (Epoch, CC BY 4.0) -- parent per --gpqa-parent:
                         'maths' (default) files it under the new application
                         "Mathematical and scientific reasoning" (id 14), which keeps
                         the 2025 GPQA surge out of the published reading-comprehension
                         column; 'qa' preserves the door-demo placement.
                       Theory of Mind on ToMBench (conversation, id 3)
                       SWE-bench Verified via Epoch (software, id 4, system_level)

What is in the DEFAULT build and what awaits a flip:
  * published construction throughout (FRS18 matrix, delta=2 discount, allapps as the
    published survivors sum). The Claude 12x58 matrix and the discount retirement are
    produced by mapping/code/build_2024_variants.py and land as one methodological step
    with the matrix decision; they are exposure-side variants and do not touch this
    script's progress splice.
  * conversation and software get EXPOSURE columns (their FRS18 matrix rows are exact
    matches); maths/science gets a PROGRESS series only, because its FRS18 row is a
    'close' match ("solving constrained, well-specified technical problems") and using
    it is a research judgement reserved for the matrix decision.
  * publication panels carry the frozen 11 application columns by default
    (--membership plus-new adds conversat and software).

Gates, each fatal:
  G1  splice integrity: every 2010-2023 row of the assembled preliminary panel is
      bit-identical to the frozen checkpoint (it is copied, and the gate proves it).
  G2  publication seam: every 2010-2023 row of every publication panel equals the
      frozen pipeline's own publication output (data/out/Publication) on all
      daioe_*/pctl_rank_* columns, exact at float32. The frozen pipeline output is
      the right target because percentile ranks on all-tie year groups are
      order-dependent and validated tie-aware against the Stata reference; see
      gate_publication_seam.
  G3  entry discipline: no new-domain column carries a value before 2024.

Output: data/vintage/<tag>/ (out/ + Publication/) and reports/<tag>/RELEASE.md.
Nothing under data/ is tracked; the script is the reproducible artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daioe import config as cfgmod  # noqa: E402
from daioe import stage2_ai_progress as s2  # noqa: E402
from daioe import stage4_index as s4  # noqa: E402
from daioe import stage5_taxonomies as s5  # noqa: E402
from daioe import io as dio  # noqa: E402

TAG = "vintage_2025_20260808"
FROZEN_OUT = ROOT / "data" / "out"
FROZEN_PUB = ROOT / "data" / "out" / "Publication"

UPDATES = [
    "data/updates/measures_updates_2024plus.xlsx",
    "data/updates/measures_updates_epoch_2026-08-07.xlsx",
]
EXT_TOMBENCH = "data/updates/extension_tombench_2026-08-08.xlsx"
EXT_SWEBENCH = "data/updates/extension_swebench_2026-08-08.xlsx"
EXT_GPQA_QA = "data/updates/extension_gpqa_2026-08-07.xlsx"
EXT_GPQA_MATHS = "data/updates/extension_gpqa_maths_2026-08-08.xlsx"
EXT_AGENTCO = "data/updates/extension_agentcompany_2026-08-08.xlsx"
EXT_METR = "data/updates/extension_metr_2026-08-13.xlsx"
EXT_METR80 = "data/updates/extension_metr80_2026-08-24.xlsx"
# Admitted 24 Aug 2026 (decision 4, Lodefalk & Engberg): the three staged Epoch
# series plus GDPval. OSWorld and GDPval thicken the agentic basket alongside the
# METR primary (within-application averaging, disclosed); MATH Level 5 thickens
# maths/science; SimpleBench thickens language comprehension and QA.
EXT_ADMITTED_20260824 = [
    "data/updates/extension_osworld_2026-08-24.xlsx",
    "data/updates/extension_mathlevel5_2026-08-24.xlsx",
    "data/updates/extension_simplebench_2026-08-24.xlsx",
    "data/updates/extension_gdpval_2026-08-24.xlsx",
]

MATHS_PARENT = "Mathematical and scientific reasoning"
NEW_CATEGORIES = ["conversat", "software"]          # exposure-capable today (exact FRS18 rows)
PUBLISHED_13 = ["allapps", "stratgames", "videogames", "imgrec", "imgcompr", "imggen",
                "readcompr", "lngmod", "translat", "speechrec", "roe", "genai", "redux"]
PUBLICATION_11 = ["allapps", "stratgames", "videogames", "imgrec", "imgcompr", "imggen",
                  "readcompr", "lngmod", "translat", "speechrec", "genai"]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build_gpqa_maths_workbook() -> Path:
    """Derive the maths-parent GPQA workbook from the committed QA-parent one."""
    src = ROOT / EXT_GPQA_QA
    dst = ROOT / EXT_GPQA_MATHS
    xl = pd.ExcelFile(src)
    meas, metr = xl.parse("measures"), xl.parse("metrics")
    meas["parent_name"] = MATHS_PARENT
    metr["parent_name"] = MATHS_PARENT
    with pd.ExcelWriter(dst) as xw:
        meas.to_excel(xw, sheet_name="measures", index=False)
        metr.to_excel(xw, sheet_name="metrics", index=False)
    return dst


def both_years_mean_from_chain(sl: pd.DataFrame, chain_year: int = 2024) -> pd.DataFrame:
    """The allapps mean rule, applied from the chain point forward only.

    Equal-weight mean over applications present in both t-1 and t (the settled
    recommendation, DECISION-allapps-sum-vs-mean): each application's progress is
    divided by the number of applications present in both years, and entrants are
    excluded in their entry year, which is what makes subdomain entry composition-
    neutral. Years before the chain point are left untouched -- the frozen window
    is the published sum and the splice discards pre-chain rows anyway.
    """
    d = sl.copy()
    present = {(r.parent_name, r.year) for r in d.itertuples()}
    post = d["year"] >= chain_year
    in_both = pd.Series(
        [(p, y - 1) in present for p, y in zip(d["parent_name"], d["year"])], index=d.index
    )
    d.loc[post & ~in_both, "mean"] = 0.0
    n = (
        d[post & in_both].groupby("year")["parent_name"].nunique().rename("_N")
    )
    d = d.merge(n, on="year", how="left")
    scale = post & d["_N"].notna()
    d.loc[scale, "mean"] = (
        (d.loc[scale, "mean"] / d.loc[scale, "_N"]).astype(np.float32).astype(np.float64)
    )
    return d.drop(columns="_N")


def make_vintage_config(args, out_dir: Path) -> cfgmod.Config:
    raw = yaml.safe_load((ROOT / "config-refresh2024.yaml").read_text())
    raw["year_final"] = 2025
    raw["benchmark_updates"] = UPDATES
    gpqa = EXT_GPQA_MATHS if args.gpqa_parent == "maths" else EXT_GPQA_QA
    # The agentic series. METR is the pre-declared PRIMARY (B3) and became available
    # when its permission arrived on 13 Aug; TheAgentCompany was the interim that
    # shipped in the default v2025 build. Magnus took the switch on 18 Aug without
    # waiting for the anchor convention, so the DEFAULT is metr and the reversal is
    # one flag, exactly as --genai legacy reverses the composite decision.
    # metr80: the successor bar, decided by Magnus 24 Aug 2026 after the 50%
    # frontier crossed the 960-minute suite bound in 2026 data. Same pinned
    # suite, stricter reliability; p50 and p80 are never in the basket together.
    agentic = {"metr": EXT_METR, "metr80": EXT_METR80,
               "agentcompany": EXT_AGENTCO}[args.agentic]
    raw["benchmark_extensions"] = [gpqa, EXT_TOMBENCH, EXT_SWEBENCH, agentic] + EXT_ADMITTED_20260824
    raw["app_categories"] = PUBLISHED_13 + NEW_CATEGORIES
    raw["app_categories_publication"] = (
        PUBLICATION_11 + (NEW_CATEGORIES if args.membership == "plus-new" else [])
    )
    # genai keeps its NAME and broadens its MEMBERSHIP at the chain point (Magnus,
    # 8 Aug): the 2023-era definition {image generation, language modeling} no longer
    # spans generative AI, whose 2024-25 frontier is conversation, software and
    # reasoning. Broad = {5, 7, 3, 4}: the new members with EXACT FRS18 matrix rows,
    # so the progress and exposure sides of the column carry the same membership.
    # Maths/science (14) and agentic (13) join via the matrix decision and the METR
    # licence respectively. The splice keeps published genai 2010-2023 bit-frozen
    # either way; reverting is --genai legacy. redux stays the complement of the
    # LEGACY genai until the matrix decision revisits both.
    if args.genai == "broad":
        raw["app_id_membership"] = dict(raw.get("app_id_membership") or {})
        raw["app_id_membership"]["genai"] = [5, 7, 3, 4]
    raw["paths"] = dict(raw["paths"])
    raw["paths"]["out"] = str(out_dir.relative_to(ROOT))
    return cfgmod.Config(raw=raw, root=ROOT)


def splice_preliminary(frozen: pd.DataFrame, ext: pd.DataFrame,
                       categories: list[str]) -> pd.DataFrame:
    """Frozen rows through 2023 verbatim; 2024-2025 rows appended with cumulative
    columns chained on the frozen 2023 level. New-domain columns are NaN before 2024
    (a series is silent before its data begin) and chain from zero.

    ROW ORDER IS LOAD-BEARING and both blocks keep their native (stage 4, year-major)
    order: Stata's percentile rank is order-dependent within tied groups, and years in
    which an application's cumulative is uniformly zero (e.g. reading comprehension
    2013) are pure-tie groups whose published ranks reproduce only under the frozen
    checkpoint's own row order. Do not re-sort this frame.
    """
    frozen = frozen.copy()
    new_cols = [c for c in ext.columns if c not in frozen.columns]
    for c in new_cols:
        frozen[c] = np.nan

    post = ext[ext["year"] >= 2024].copy()   # native stage-4 order preserved
    base23 = frozen[frozen["year"] == 2023].set_index("occ_code_onet")
    assert set(post["occ_code_onet"]) == set(base23.index), (
        "occupation sets differ between frozen and extended runs"
    )
    # Chain the cumulative on the frozen 2023 level. Computed on a key-sorted COPY,
    # then mapped back, so the physical row order above is never disturbed.
    calc = post[["occ_code_onet", "year"]].copy()
    for app in categories:
        ch, cu = f"exp_change_{app}", f"exp_cumul_{app}"
        if ch not in post.columns:
            continue
        tmp = post[["occ_code_onet", "year", ch]].sort_values(
            ["occ_code_onet", "year"], kind="mergesort"
        )
        base = tmp["occ_code_onet"].map(
            base23[cu] if cu in base23.columns else pd.Series(dtype=float)
        ).fillna(0.0)
        run = tmp.groupby("occ_code_onet", sort=False)[ch].cumsum().fillna(0.0)
        tmp[cu] = (base + run).astype(np.float32).astype(np.float64)
        lut = tmp.set_index(["occ_code_onet", "year"])[cu]
        post[cu] = pd.MultiIndex.from_frame(calc).map(lut)

    return pd.concat([frozen, post[frozen.columns]], ignore_index=True)


def gate_publication_seam(vintage_pub_dir: Path) -> list[str]:
    """G2: every publication panel's 2010-2023 rows equal the FROZEN PIPELINE's own
    publication output (data/out/Publication) on all daioe_*/pctl_rank_* columns,
    exact at float32.

    The comparison target is the pipeline's own frozen build, not Erik's Stata files,
    for one precise reason: percentile ranks on all-tie year groups (e.g. reading
    comprehension 2013, where every occupation's cumulative is exactly zero) are
    order-dependent, and Stata's historical row order is not recoverable. The frozen
    pipeline output passed the tie-aware validation against the Stata reference
    (60/60 percentile columns); the vintage must extend THAT build bit-for-bit. The
    chain is: vintage == frozen pipeline (this gate, exact) ~= Stata reference
    (tie-aware, already validated).
    """
    lines = []
    taxmap = {
        "daioe_onetsoc2010.dta": ["occ_code_onetsoc2010", "year"],
        "daioe_soc2010.dta": ["occ_code_soc2010", "year"],
        "daioe_isco08.dta": ["occ_code_isco08", "year"],
        "daioe_ssyk2012.dta": ["ssyk2012_4", "year"],
        "daioe_ssyk96.dta": ["ssyk96_4", "year"],
    }
    for fname, keys in taxmap.items():
        got = dio.read_dta(vintage_pub_dir / fname)
        ref = dio.read_dta(FROZEN_PUB / fname)
        # PL-M2 (closed 24 Aug 2026): a column that silently disappeared from the
        # vintage would previously be skipped by the intersection below; now it fails.
        missing = [c for c in ref.columns
                   if c.startswith(("daioe_", "pctl_rank_")) and c not in got.columns]
        assert not missing, f"{fname}: G2 FAILED, columns missing from the vintage: {missing}"
        cols = [c for c in ref.columns
                if c.startswith(("daioe_", "pctl_rank_")) and c in got.columns]
        g = got[got["year"] <= 2023].set_index(keys)[cols].sort_index()
        r = ref[ref["year"] <= 2023].set_index(keys)[cols].sort_index()
        assert g.index.equals(r.index), f"{fname}: 2010-2023 row sets differ"
        diff = (g.astype("float32").fillna(-9e9).values
                != r.astype("float32").fillna(-9e9).values).sum()
        lines.append(f"{fname}: {len(g)} published rows, {len(cols)} columns, "
                     f"{int(diff)} cells differ")
        assert diff == 0, f"{fname}: G2 FAILED, {int(diff)} published cells changed"
    return lines


def gate_internal_seam(vintage_out: Path) -> list[str]:
    """G2b: every INTERNAL taxonomy panel's 2010-2023 rows equal the frozen pipeline's
    own internal panel on all shared numeric columns, exact at float32.

    This exists chiefly for SOC2018, which has NO publication panel (and no Stata
    reference; its own verification is the BLS round-trip check), so the publication
    seam gate never touches it. The other five internals are covered here too because
    the gate is cheap and strictly stronger than gating publication alone.
    """
    lines = []
    taxmap = {
        "daioe_panel_onet.dta": ["occ_code_onet", "year"],
        "daioe_panel_soc.dta": ["occ_code_soc", "year"],
        "daioe_panel_isco08.dta": ["ISCO08code_str", "year"],
        "daioe_panel_ssyk2012.dta": ["ssyk2012_4", "year"],
        "daioe_panel_ssyk96.dta": ["ssyk96_4", "year"],
        "daioe_panel_soc2018.dta": ["SOC2018code", "year"],
    }
    for fname, keys in taxmap.items():
        got = dio.read_dta(vintage_out / fname)
        ref = dio.read_dta(FROZEN_OUT / fname)
        # PL-M2 (closed 24 Aug 2026): same completeness assert as G2.
        missing = [c for c in ref.columns
                   if c not in keys and ref[c].dtype.kind in "fc" and c not in got.columns]
        assert not missing, f"{fname}: G2b FAILED, columns missing from the vintage: {missing}"
        cols = [c for c in ref.columns
                if c not in keys and ref[c].dtype.kind in "fc" and c in got.columns]
        g = got[got["year"] <= 2023].set_index(keys)[cols].sort_index()
        r = ref[ref["year"] <= 2023].set_index(keys)[cols].sort_index()
        assert g.index.equals(r.index), f"{fname}: 2010-2023 row sets differ"
        diff = (g.astype("float32").fillna(-9e9).values
                != r.astype("float32").fillna(-9e9).values).sum()
        lines.append(f"{fname}: {len(g)} published rows, {len(cols)} columns, "
                     f"{int(diff)} cells differ")
        assert diff == 0, f"{fname}: G2b FAILED, {int(diff)} published cells changed"
    return lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpqa-parent", choices=["maths", "qa"], default="maths")
    ap.add_argument("--allapps-rule", choices=["survivors", "mean"], default="survivors")
    ap.add_argument("--membership", choices=["published", "plus-new"], default="published")
    ap.add_argument("--genai", choices=["broad", "legacy"], default="broad")
    ap.add_argument("--agentic", choices=["metr", "metr80", "agentcompany"], default="metr80",
                    help="agentic series: METR task horizons (default, primary) or "
                         "TheAgentCompany (the interim that shipped in v2025)")
    ap.add_argument("--tag", default=TAG)
    args = ap.parse_args()

    vintage_dir = ROOT / "data" / "vintage" / args.tag
    out_dir = vintage_dir / "out"
    report_dir = ROOT / "reports" / args.tag
    for d in (out_dir, report_dir):
        d.mkdir(parents=True, exist_ok=True)

    # frozen stage 1-3 checkpoints feed stage 4 unchanged.
    for p in FROZEN_OUT.glob("*.parquet"):
        shutil.copy(p, out_dir / p.name)

    if args.gpqa_parent == "maths":
        build_gpqa_maths_workbook()

    cfg = make_vintage_config(args, out_dir)
    print(f"[1/6] stage 2 extended run (year_final 2025, {len(cfg.benchmark_extensions)} "
          f"extensions, gpqa-parent={args.gpqa_parent}) ...")
    s2.run(cfg, validate=False)

    if args.allapps_rule == "mean":
        p = out_dir / "slopes_slimmed_allapps.parquet"
        sl = pd.read_parquet(p)
        both_years_mean_from_chain(sl).to_parquet(p, index=False)
        print("      allapps rule: both-years mean applied from 2024 forward")

    print("[2/6] stage 4 exposure panels ...")
    panels = s4.build(cfg)

    print("[3/6] splice at the occupation level (seam policy: freeze history) ...")
    frozen_prelim = pd.read_parquet(FROZEN_OUT / "daioe_panel_onet_preliminary.parquet")
    spliced = splice_preliminary(frozen_prelim, panels["preliminary"], cfg.app_categories)
    spliced.to_parquet(out_dir / "daioe_panel_onet_preliminary.parquet", index=False)

    # G1: the frozen window is copied, and this proves the copy. The splice re-sorts,
    # so compare aligned on (occupation, year), not by position.
    keys = ["occ_code_onet", "year"]
    shared = [c for c in frozen_prelim.columns
              if c not in keys and frozen_prelim[c].dtype.kind in "fc"]
    a = spliced[spliced["year"] <= 2023].set_index(keys)[shared].sort_index()
    b = frozen_prelim.set_index(keys)[shared].sort_index()
    assert a.index.equals(b.index), "G1 FAILED: frozen-window row set changed"
    d = (a.fillna(-9e9).values != b.fillna(-9e9).values).sum()
    assert d == 0, f"G1 FAILED: {int(d)} frozen preliminary cells changed"
    print(f"      G1 splice integrity: {len(b)} frozen rows x {len(shared)} columns, 0 changed")

    # G3: entry discipline on the new-domain columns.
    for app in NEW_CATEGORIES:
        ch = f"exp_change_{app}"
        if ch in spliced.columns:
            early = spliced[(spliced["year"] < 2024) & spliced[ch].notna()]
            assert early.empty, f"G3 FAILED: {app} carries values before 2024"
    print("      G3 entry discipline: new-domain columns silent before 2024")

    print("[4/6] stage 5 taxonomy fan-out + publication exports ...")
    s5.run(cfg, validate=False)

    print("[5/6] G2 publication + G2b internal seam gates ...")
    g2 = gate_publication_seam(out_dir / "Publication")
    for line in g2:
        print("      " + line)
    g2b = gate_internal_seam(out_dir)
    for line in g2b:
        print("      internal " + line)

    print("[6/6] release report ...")
    ext_sl = pd.read_parquet(out_dir / "metrics_frontiers.parquet")  # provenance only
    slopes_files = sorted(out_dir.glob("slopes_slimmed_*.parquet"))
    coverage = []
    for p in slopes_files:
        app = p.stem.replace("slopes_slimmed_", "")
        sl = pd.read_parquet(p)
        for yr in (2024, 2025):
            r = sl[sl["year"] == yr]
            if len(r) and app not in ("roe",):
                coverage.append({"category": app, "year": yr,
                                 "applications": int(r["parent_name"].nunique()),
                                 "benchmarks": int(r["count"].sum())})
    cov = pd.DataFrame(coverage)

    onet_pub = dio.read_dta(out_dir / "Publication" / "daioe_onetsoc2010.dta")
    n24 = int((onet_pub["year"] == 2024).sum())
    n25 = int((onet_pub["year"] == 2025).sum())

    inputs = UPDATES + list(map(str, [
        EXT_GPQA_MATHS if args.gpqa_parent == "maths" else EXT_GPQA_QA,
        EXT_TOMBENCH, EXT_SWEBENCH, EXT_AGENTCO,
    ]))
    manifest = {p: sha256(ROOT / p) for p in inputs}

    report = report_dir / "RELEASE.md"
    with open(report, "w") as fh:
        fh.write(f"# DAIOE 2025 vintage — release assembly ({args.tag})\n\n")
        fh.write(f"Flags: gpqa-parent={args.gpqa_parent}, allapps-rule={args.allapps_rule}, "
                 f"membership={args.membership}, genai={args.genai}, "
                 f"agentic={args.agentic}\n\n")
        fh.write("## Seam policy\nFrozen 2010-2023 published values immutable; 2024-2025 "
                 "increments computed on the fuller archive and chained at 2023 "
                 "(checkpoint2 decision, 2026-07-07). Entry-timing doctrine: "
                 "notes/DESIGN-entry-timing-and-freeze_2026-08-08.md.\n\n")
        fh.write("## Gates\n- G1 splice integrity: PASSED (0 frozen cells changed)\n")
        for line in g2:
            fh.write(f"- G2 {line}\n")
        for line in g2b:
            fh.write(f"- G2b internal {line}\n")
        fh.write("- G3 entry discipline: PASSED (new-domain columns silent before 2024)\n\n")
        fh.write(f"## Panel\nONET publication panel rows: 2024: {n24}, 2025: {n25}.\n\n")
        fh.write("## Coverage (appended years)\n\n")
        fh.write(cov.to_string(index=False) + "\n\n")
        fh.write("Coverage caveat: the release gate requires track-a-coverage-audit.md "
                 "attached to any circulated 2024+ value; five of nine frozen applications "
                 "have no 2025 source (archive death, not capability plateau).\n\n")

        # First-measured-year caveat: a new series' first progress year is measured
        # against its entry-year frontier, and a THIN entry-year baseline shifts
        # late-entry-year capability into the first measured year. Disclose the
        # baseline count and frontier per admitted series so the reader can judge.
        fh.write("## First-measured-year caveat (new series)\n\n")
        fh.write("A series chained at 2024 contributes nothing in 2024 and its 2025 "
                 "progress is measured against the 2024 frontier. Where the 2024 "
                 "baseline rests on few observations, capability released late in 2024 "
                 "but not yet in the harness inflates the first measured year; a later "
                 "vintage may revise it (vintages are labelled objects; frozen window "
                 "unaffected).\n\n")
        for label, wb in [("GPQA Diamond", inputs[2]), ("ToMBench", EXT_TOMBENCH),
                          ("SWE-bench Verified", EXT_SWEBENCH),
                          ("TheAgentCompany (INTERIM, pending METR)", EXT_AGENTCO)]:
            m = pd.read_excel(ROOT / wb, sheet_name="measures")
            yr = pd.to_datetime(m["date"]).dt.year
            b = m[yr == 2024]
            if len(b):
                top = b.loc[b["value"].idxmax()]
                fh.write(f"- {label}: 2024 baseline n={len(b)}, frontier {top['value']:.1f} "
                         f"({top['name']})\n")
            else:
                fh.write(f"- {label}: no 2024 observations\n")
        fh.write("\nSWE-bench is the thin case (n=1; no o1-class late-2024 model in the "
                 "Epoch harness), and it drives the broadened genai composite's 2025 "
                 "step; treat that step as an upper bound pending Epoch backfill.\n\n")
        fh.write("## Erik flips (15 Aug)\n"
                 "1. Matrix adoption + discount: exposure-side variants via "
                 "mapping/code/build_2024_variants.py (R0/matrix/social panels); land "
                 "together with this splice as the one chain point when decided.\n"
                 "2. allapps mean: re-run with --allapps-rule mean.\n"
                 "3. GPQA placement: --gpqa-parent qa restores the door-demo placement.\n"
                 "4. Composite membership: --membership plus-new adds conversat+software "
                 "to publication columns.\n"
                 "4b. genai membership: KEEPS ITS NAME, broadens at the chain point to "
                 "{imggen, lngmod, conversation, software} (default; Magnus 8 Aug); "
                 "maths joins with the matrix decision, agentic with METR; revert "
                 "with --genai legacy. redux remains the legacy complement for now.\n"
                 "5. Anchor convention: SWE-bench ceiling anchor 95.0 is PROVISIONAL "
                 "(notes/EXTENSION-software-swebench_2026-08-08.md). It now covers "
                 "THREE ceiling cases and two kinds, since METR's 960-minute anchor "
                 "is an instrument ceiling and not a human score at all.\n"
                 "6. TAKEN 18 Aug, not waiting on the convention: the agentic series "
                 "is METR (--agentic metr, the default here); TheAgentCompany, the "
                 "interim that shipped in the 8 Aug build, is demoted. Reversal is "
                 "--agentic agentcompany, and this vintage is tagged separately from "
                 "the shipped one so the reversal costs nothing. What was NOT taken: "
                 "agentic stays OUT of the genai composite (4b), because that is a "
                 "headline column and the reversible half of the decision is the "
                 "series, not the composite. NOTE the consequence, disclosed rather "
                 "than discovered: agentic 2025 moves 2.2051 against 0.2194 for the "
                 "next-largest application, and the capability transform does NOT "
                 "damp it (stage 2b is within-basket). Part of that gap is the other "
                 "baskets being dead rather than agentic being hot: five of nine "
                 "original applications have no living 2025 source. See "
                 "notes/EXTENSION-agentic-metr_2026-08-13.md.\n\n")
        fh.write("## Input manifest (sha256)\n\n")
        for p, h in manifest.items():
            fh.write(f"- `{p}`  {h[:16]}…\n")
        fh.write("\nMaths/science carries a PROGRESS series only in this build: its FRS18 "
                 "matrix row is a close match, not exact, and using it is a research "
                 "judgement reserved for the matrix decision. Conversation and software "
                 "have exact FRS18 rows and carry exposure columns.\n")
    print(f"\nwrote {report.relative_to(ROOT)}")
    print(f"vintage panels in {vintage_dir.relative_to(ROOT)}/out (+ Publication/)")


if __name__ == "__main__":
    main()
