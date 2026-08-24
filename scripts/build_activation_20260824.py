"""Activate agentic and maths/science exposure columns (D1b approved 24 Aug 2026).

Basis: the two FRS 2018 expert rows, unedited, approved by Magnus 24 Aug after
the FRS-LLM certification (held-out 0.803 / 0.787) and the two-rows exhibit.
Construction: identical to every other per-application exposure column -- raw
application progress through the matrix row, occupation ability weights, the
social discount at delta=2, the square, cumulation. Chained: both series enter
at 2024 from zero; no frozen value can move because the columns are new.

Outputs: data/vintage/g2_20260824/activated_{agentic,mathsci}_panel_onet.parquet
and a short ACTIVATION-REPORT.md.
"""
import importlib.util, re, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("bv", ROOT / "mapping/code/build_2024_variants.py")
bv = importlib.util.module_from_spec(spec); spec.loader.exec_module(bv)
VIN = ROOT / "data/vintage/vintage_2025_admitted_20260824/out"
OUT = ROOT / "data/vintage/g2_20260824"
bv.OUT = VIN

frames = []
for f in sorted(VIN.glob("slopes_slimmed_*.parquet")):
    d = pd.read_parquet(f)
    if "application" in d.columns:
        frames.append(d[["application", "year", "mean"]])
prog = (pd.concat(frames).drop_duplicates(["application", "year"])
        .rename(columns={"mean": "progress"}))

ab = (pd.read_csv(ROOT / "mapping/raw_data/abilities_v2.csv")
      .drop_duplicates("ability_id").set_index("ability_id")["ability_name"])
name_to_id = {v.strip().lower(): k for k, v in ab.items()}
frs = pd.read_excel(ROOT / "mapping/raw_data/mapping_matrix.xlsx",
                    sheet_name="Combined").set_index("abilities")
w52, _ = bv.load_weights(None)
social = bv.load_social_score(2.0)

ROWS = {"agentic task execution": "solving real-world technical problems",
        "mathematical and scientific reasoning": "solving constrained, well-specified technical problems"}
rep = ["# Activation report, 24 Aug 2026 (D1b approved: FRS 2018 rows, unedited)\n"]
for app, frs_row in ROWS.items():
    f_raw = frs.loc[frs_row].drop("ability_id")
    r = pd.Series({name_to_id.get(str(n).strip().lower()): float(v) for n, v in f_raw.items()})
    M = pd.DataFrame([r]).rename(index={0: app})
    M.columns = [re.sub(r"[^a-z]", "", str(ab.get(i, "")).lower()) for i in M.columns]
    M = M.loc[:, [c for c in M.columns if c]]
    panel = bv.build_panel(M, w52, prog[prog.application == app], social, 10.0)
    tag = "agentic" if "agentic" in app else "mathsci"
    panel.to_parquet(OUT / f"activated_{tag}_panel_onet.parquet", index=False)
    p25 = panel[panel.year == 2025]
    rep.append(f"- {app}: {panel.occ_code_onet.nunique()} occupations, years "
               f"{int(panel.year.min())}-{int(panel.year.max())}; 2025 exposure "
               f"mean {p25.exp_cumul.mean():.3f}, IQR "
               f"{p25.exp_cumul.quantile(.25):.3f}-{p25.exp_cumul.quantile(.75):.3f}")
(OUT.parent / "g2_20260824" / "ACTIVATION-REPORT.md").write_text("\n".join(rep))
print("\n".join(rep))
