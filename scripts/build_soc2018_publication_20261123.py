"""Publication-format SOC 2018 files for the v1.1.1 scores bundle (23 Nov 2026).

Why: up to v1.1.0 the SOC 2018 scores shipped only as the internal stage-5 panel
(`daioe_panel_soc2018.dta`), with pipeline-native names (`exp_cumul`,
`exp_cumul_genai`, ...), exp_change columns, occupation characteristics and
comparator measures. Every other classification ships in publication format
(`daioe_<app>`, `pctl_rank_<app>`, `pctl_mid_<app>`). A user moving between SOC 2010
and SOC 2018 met two names for one variable (a PhD student asked exactly that,
23 Nov 2026). This script closes the gap. It changes no value; it renames, selects
and adds the two percentile companions.

What it does, for each window (frozen 2010-2023, vintage 2025):
  1. reads the internal SOC 2018 panel the bundle already ships;
  2. renames exp_cumul -> daioe_allapps and exp_cumul_<app> -> daioe_<app> for the
     published applications (config `app_categories_publication`, plus, in the 2025
     vintage, the five columns every other vintage-2025 panel carries);
  3. computes pctl_rank_<app> with the pipeline's own legacy rule (stata_ops.pctl_rank)
     and pctl_mid_<app> with the tie-invariant midrank rule of add_midrank_pctl;
  4. keeps the crosswalk flags n_soc2010_sources and is_split, which only SOC 2018 needs;
  5. writes daioe_soc2018.dta / .tsv / .xlsx.

Checks (fatal):
  * every daioe_* cell equals its exp_cumul source exactly (pure rename);
  * on clean 1:1 SOC2010->SOC2018 pairs, every daioe_* value equals the SOC 2010
    publication file of the same window exactly;
  * pctl_mid_* is tie-invariant; pctl_rank_allapps equals the panel's own column.

Missing cells: SOC 2018, like ISCO-08 and SSYK, is crosswalked from SOC 2010, and the
crosswalk rule turns an exact-zero cumulative into missing. Composites with no
measured progress yet (genai, g2gen in 2010-2011) are therefore missing here, as in
ISCO-08 and SSYK, where SOC 2010 and O*NET-SOC show zero. Left as is, on purpose:
it matches the other crosswalked classifications. Documented in VINTAGES.md.

Usage:  python scripts/build_soc2018_publication_20261123.py
Output: data/derived/soc2018_publication/{frozen-2010-2023,vintage-2025}/daioe_soc2018.*
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from daioe import io as dio  # noqa: E402
from daioe import stata_ops as so  # noqa: E402
from daioe.config import load_config  # noqa: E402

OUT = ROOT / "data" / "derived" / "soc2018_publication"
CW = ROOT / "data" / "derived" / "soc2010_to_soc2018_BLS.csv"

# (output folder, internal SOC 2018 panel, SOC 2010 publication file of the same window)
WINDOWS = [
    ("frozen-2010-2023",
     ROOT / "data" / "out" / "daioe_panel_soc2018.dta",
     ROOT / "data" / "reference" / "Publication" / "daioe_soc2010.dta"),
    ("vintage-2025",
     ROOT / "data" / "vintage" / "vintage_2025_v110rc3_20260905" / "out" / "daioe_panel_soc2018.dta",
     ROOT / "data" / "vintage" / "vintage_2025_v110rc3_20260905" / "out" / "Publication" / "daioe_soc2010.dta"),
]
# Columns the vintage-2025 publication panels carry beyond the legacy eleven.
V2025_EXTRA = ["g2all", "g2gen", "g2nine", "agentic", "mathsci"]


def build(panel_path: Path, extra_apps: list[str]) -> pd.DataFrame:
    """Rename and select one internal SOC 2018 panel into publication format."""
    cfg = load_config(ROOT / "config.yaml")
    p = dio.read_dta(panel_path)
    # The crosswalk panels drop the suffix on the all-applications column.
    p = p.rename(columns={"exp_cumul": "exp_cumul_allapps"})

    apps = list(cfg.app_categories_publication) + [a for a in extra_apps
                                                   if f"exp_cumul_{a}" in p.columns]
    missing = [a for a in extra_apps if f"exp_cumul_{a}" not in p.columns]
    assert not missing, f"{panel_path.name}: expected columns absent: {missing}"

    df = p[["SOC2018code", "SOC2018title", "year", "n_soc2010_sources", "is_split"]].copy()
    df = df.rename(columns={"SOC2018code": "occ_code_soc2018",
                            "SOC2018title": "occ_title_soc2018"})
    for a in apps:
        df[f"daioe_{a}"] = p[f"exp_cumul_{a}"].astype("float32")
        # pure rename: same cells, same missingness
        assert df[f"daioe_{a}"].equals(p[f"exp_cumul_{a}"].astype("float32")), a

    # Stable order first, so the legacy tie rule (input order) is deterministic.
    df = df.sort_values(["occ_code_soc2018", "year"], kind="mergesort").reset_index(drop=True)
    for a in apps:
        df[f"pctl_rank_{a}"] = so.f32(so.pctl_rank(df, value=f"daioe_{a}", out=f"pctl_rank_{a}"))
    for a in apps:
        df[f"pctl_mid_{a}"] = so.f32(
            df.groupby("year")[f"daioe_{a}"].rank(method="average", pct=True) * 100.0)

    order = (["occ_code_soc2018", "occ_title_soc2018", "year"]
             + [f"daioe_{a}" for a in apps] + [f"pctl_rank_{a}" for a in apps]
             + [f"pctl_mid_{a}" for a in apps] + ["n_soc2010_sources", "is_split"])
    df = df[order]
    df["year"] = df["year"].astype("float32")

    # pctl_rank_allapps must reproduce the panel's own column (same rule, same input)
    src = (p.sort_values(["SOC2018code", "year"], kind="mergesort")
            .reset_index(drop=True)["pctl_rank_allapps"].astype("float32"))
    assert (df["pctl_rank_allapps"].fillna(-1) == src.fillna(-1)).all(), \
        "pctl_rank_allapps differs from the internal panel"
    # tie invariance of the midranks
    for a in apps:
        g = df[["year", f"daioe_{a}", f"pctl_mid_{a}"]].dropna()
        assert (g.groupby(["year", f"daioe_{a}"])[f"pctl_mid_{a}"].nunique() <= 1).all(), a
    return df, apps


def check_against_soc2010(df: pd.DataFrame, apps: list[str], soc2010_path: Path) -> int:
    """On clean 1:1 crosswalk pairs the SOC 2018 value must equal the SOC 2010 value."""
    cw = pd.read_csv(CW, dtype=str)
    one = cw[(cw.n_soc2010_sources == "1") & (cw.n_soc2018_targets == "1")]
    s10 = dio.read_dta(soc2010_path)
    m = (one[["SOC2010code", "SOC2018code"]]
         .merge(s10, left_on="SOC2010code", right_on="occ_code_soc2010")
         .merge(df, left_on=["SOC2018code", "year"], right_on=["occ_code_soc2018", "year"],
                suffixes=("_10", "_18")))
    assert len(m) > 0, "no 1:1 rows matched"
    for a in apps:
        x, y = m[f"daioe_{a}_10"].astype("float32"), m[f"daioe_{a}_18"].astype("float32")
        both = x.notna() & y.notna()
        assert (x[both] == y[both]).all(), f"daioe_{a}: SOC 2018 differs from SOC 2010 on 1:1 pairs"
        # missing only where the crosswalk rule applies: SOC 2010 shows exactly zero
        only10 = x.notna() & y.isna()
        assert (x[only10] == 0).all(), f"daioe_{a}: missing in SOC 2018 where SOC 2010 is non-zero"
        assert not (x.isna() & y.notna()).any(), f"daioe_{a}: value in SOC 2018, missing in SOC 2010"
    return len(m)


def main() -> None:
    for folder, panel, soc2010 in WINDOWS:
        extra = V2025_EXTRA if folder == "vintage-2025" else []
        df, apps = build(panel, extra)
        n = check_against_soc2010(df, apps, soc2010)
        dst = OUT / folder
        dio.write_dta(df, dst / "daioe_soc2018.dta")
        dio.write_csv_tab(df, dst / "daioe_soc2018.tsv")
        dio.write_xlsx(df, dst / "daioe_soc2018.xlsx")
        print(f"{folder}: {len(df)} rows, {df.occ_code_soc2018.nunique()} codes, "
              f"{len(apps)} indices; 1:1 check against SOC 2010 passed on {n} rows")


if __name__ == "__main__":
    main()
