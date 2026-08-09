"""
F2 randomisation-inference generator (Panel C item F2; OA Section P).

Null: the CLERICAL decline reflects the ARRIVAL TIMING of capability, not any
smooth force on the same occupational gradient. Implementation: permute the
nine applications' capability-path SHAPES across application slots, holding
each slot's total 2010-2023 capability mass and every loading fixed, rebuild
occupation-year exposure, and emit 200 permuted SSYK2012-level panels plus the
identity draw for register round B41z.

Pure released-panel algebra, justified by the paper's Eq. (5) expansion (OA
Section P): the per-application increment factorises as
X_d,ot = (w_o a_od)^2 (dp_dt)^2, so Y=sqrt(X) is loading x path, the aggregate
increment is (sum_d Y_d,ot)^2, and a path-shape permutation acts as
Y'_d,ot = (sum_tau Y_d,otau) * shape_pi(d),t. Self-tests verify the two
identities this rests on before anything is written:
  T1 additive-sqrt: (sum_d sqrt(X_d))^2 == exp_change up to the documented
     aggregate-level wedge (conseq-error/admission), which is held fixed
     across draws as timing-neutral
  T2 shape constancy: Y_d,ot / sum_tau Y_d,otau identical across occupations.
Identity draw (draw 0) equals the released panel by construction; verified.

Run from the daioe-pipeline repo root. Output:
  data/out/perm_daioe_ssyk2012_year.csv   (draw, ssyk2012_4, year, exp_cumul_perm)
  data/out/perm_daioe_README.txt
Public data only; deterministic (seed 20260809).
"""
import numpy as np
import pandas as pd
from pathlib import Path

SEED = 20260809
NDRAW = 200
SUBS = ["stratgames","videogames","imgrec","imgcompr","imggen",
        "readcompr","lngmod","translat","speechrec"]

root = Path(".")
panel = pd.read_stata(root/"data/out/daioe_panel_ssyk2012.dta")
panel = panel[["ssyk2012_4","year","exp_change","exp_cumul"]
              + [f"exp_change_{s}" for s in SUBS]].copy()
panel["year"] = panel["year"].astype(int)

# Subdomain increments are NaN before a subdomain's first benchmark year; under
# cumulation-from-2010 that is zero measured progress, so fill 0. Occupations
# with no released aggregate at all (exp_change NaN) carry no exposure anywhere
# in the paper; drop them and say so.
for s in SUBS:
    panel[f"exp_change_{s}"] = panel[f"exp_change_{s}"].fillna(0.0)
nocc = panel.loc[panel["exp_change"].isna(),"ssyk2012_4"].unique()
if len(nocc):
    print(f"dropping {len(nocc)} occupations with NaN released aggregate "
          f"(no exposure in the paper either)")
    panel = panel[~panel["ssyk2012_4"].isin(nocc)].copy()

# ---- T1: additive-sqrt identity, and which subdomain set satisfies it ----
Y = {s: np.sqrt(panel[f"exp_change_{s}"].clip(lower=0)) for s in SUBS}
recon = sum(Y.values())**2
err = (recon - panel["exp_change"]).abs()
rel = err / panel["exp_change"].where(panel["exp_change"]>0)
print(f"T1 additive-sqrt (9 named subdomains): max abs err {err.max():.3e}, "
      f"median rel err {rel.median():.3e}, p99 rel {rel.quantile(0.99):.3e}")
# The nine named series close the identity up to a sub-1-per-cent wedge from
# the aggregate-level conseq-error and admission handling (documented pipeline
# divergences). The wedge W_ot = exp_change - recon is held FIXED across draws:
# it is not a function of arrival timing, so carrying it unchanged is the
# timing-neutral treatment, and it makes the identity draw exact by construction.
T1_OK = rel.median() < 1e-3 and rel.quantile(0.99) < 2e-2

# ---- T2: shape constancy across occupations ----
wide = {s: panel.pivot(index="ssyk2012_4", columns="year",
                       values=f"exp_change_{s}") for s in SUBS}
shapes = {}
T2_worst = 0.0
for s in SUBS:
    Yw = np.sqrt(wide[s].clip(lower=0))
    tot = Yw.sum(axis=1)
    sh = Yw.div(tot.where(tot>0), axis=0)          # per-occ shape
    med = sh.median(axis=0)                        # canonical shape
    med = med / med.sum()
    dev = (sh.sub(med, axis=1)).abs().max().max()
    shapes[s] = med
    T2_worst = max(T2_worst, float(dev))
    print(f"T2 shape constancy {s}: max abs dev from median shape {dev:.3e}")
T2_OK = T2_worst < 1e-6

print(f"SELF-TESTS: T1 {'PASS' if T1_OK else 'FAIL'} | T2 {'PASS' if T2_OK else 'FAIL'}")
if not (T1_OK and T2_OK):
    raise SystemExit(
        "Identities do not hold on the released panel (composites, conseq-error "
        "or admission handling breaks the factorisation). DO NOT ship: fall back "
        "to the stage-level rebuild route with Erik before B41z runs.")

# ---- build draws ----
wedgelong = (panel["exp_change"] - recon).rename("w")
wedge = pd.concat([panel[["ssyk2012_4","year"]], wedgelong], axis=1)\
          .pivot(index="ssyk2012_4", columns="year", values="w")
print(f"wedge: median rel {rel.median():.3e}; held fixed across draws")

rng = np.random.default_rng(SEED)
years = sorted(panel["year"].unique())
occ = wide[SUBS[0]].index
Ytot = {s: np.sqrt(wide[s].clip(lower=0)).sum(axis=1) for s in SUBS}  # per-occ mass

rows = []
perms = [np.arange(9)]                                   # draw 0 = identity
seen = {tuple(perms[0])}
while len(perms) < NDRAW + 1:
    cand = rng.permutation(9)
    if tuple(cand) not in seen:
        perms.append(cand); seen.add(tuple(cand))

for draw, pi in enumerate(perms):
    Yp = 0.0
    for j, s in enumerate(SUBS):
        tgt = SUBS[pi[j]]                                # slot s receives shape of tgt
        shp = shapes[tgt].reindex(years).values          # (T,)
        Yp = Yp + np.outer(Ytot[s].values, shp)          # loading*mass x shape
    Xp = Yp**2 + wedge.values                            # + fixed timing-neutral wedge
    cum = Xp.cumsum(axis=1)
    df = pd.DataFrame(cum, index=occ, columns=years).stack().rename("exp_cumul_perm").reset_index()
    df.columns = ["ssyk2012_4","year","exp_cumul_perm"]
    df.insert(0,"draw",draw)
    rows.append(df)

out = pd.concat(rows, ignore_index=True)

# identity-draw fidelity vs the released cumulative aggregate
m = out[out["draw"]==0].merge(panel[["ssyk2012_4","year","exp_cumul"]],
                              on=["ssyk2012_4","year"])
fid = np.corrcoef(m["exp_cumul_perm"], m["exp_cumul"])[0,1]
mad = (m["exp_cumul_perm"]-m["exp_cumul"]).abs().max()
print(f"IDENTITY DRAW vs released exp_cumul: corr {fid:.8f}, max abs diff {mad:.3e}")

dest = root/"data/out/perm_daioe_ssyk2012_year.csv"
out.to_csv(dest, index=False)

# MONA upload rules (reference_mona_upload, re-learned the hard way 2026-08-09):
# max 10 MB per file AND csv is not an allowed upload format. Every MONA-bound
# artefact therefore ALSO ships as .dta parts under ~8 MB; B41z reassembles
# and row-count-asserts them. The csv above stays as the local/analysis copy.
o2 = out.copy()
for c in ("draw","ssyk2012_4","year"):
    o2[c] = o2[c].astype("int16")
bounds = [(0,66),(67,133),(134,200)]
for i,(a_,b_) in enumerate(bounds,1):
    f = root/f"data/out/perm_daioe_ssyk2012_year_p{i}of3.dta"
    o2[(o2["draw"]>=a_)&(o2["draw"]<=b_)].to_stata(f, write_index=False, version=118)
    sz = f.stat().st_size/1e6
    assert sz < 9.5, f"{f} is {sz:.1f} MB: over the MONA headroom, re-split"
    print(f"WROTE {f} ({sz:.1f} MB)")
readme = root/"data/out/perm_daioe_README.txt"
readme.write_text(
 "perm_daioe_ssyk2012_year.csv - F2 randomisation-inference input for B41z\n"
 f"Generated {pd.Timestamp('2026-08-09')} from daioe_panel_ssyk2012.dta, seed {SEED}.\n"
 f"Draw 0 = identity (corr {fid:.8f} with released exp_cumul, max diff {mad:.3e});\n"
 f"draws 1-{NDRAW} permute the nine applications' capability-path shapes across\n"
 "slots, holding each slot's total 2010-2023 mass and all loadings fixed, so the\n"
 "null is arrival TIMING alone. Self-tests T1/T2 passed (see generator log).\n"
 "Columns: draw, ssyk2012_4, year, exp_cumul_perm (raw cumulative aggregate).\n"
 "Upload with the 2026-08 trip; consumed by ai_unboxed_rev_SE_B41z_ri.do.\n")
print(f"WROTE {dest} ({len(out):,} rows) + README")
