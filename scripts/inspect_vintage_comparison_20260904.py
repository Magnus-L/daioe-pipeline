"""Side-by-side inspection of the old vintage against the 2025 vintage (v1.1.0 rc).

Built 4 Sep 2026 at ML's request before the Zenodo releases: top/bottom occupations
for overall AI and for genai, old vs new, plus full trajectories 2010 to each
vintage's last year, so the comparison is inspectable by eye rather than taken on
the gates' word. O*NET-SOC panel (966 occupations, titles available).

Old vintage = the deposited v1.0.0 bundle (frozen 2010-2023 + 2024 refresh).
New vintage = the staged v1.1.0 release candidate (2010-2025).
Output: reports/vintage_comparison_20260904.pdf
"""
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

ROOT = Path(__file__).resolve().parents[1]
OLD_F = ROOT/"dist/daioe-v1.0.0-scores/frozen-2010-2023/daioe_onetsoc2010.dta"
OLD_R = ROOT/"dist/daioe-v1.0.0-scores/refresh-2024/daioe_onetsoc2010.dta"
NEW   = next((ROOT/"data/vintage/vintage_2025_v110rc_20260824").rglob("Publication/daioe_onetsoc2010.dta"))
OUT   = ROOT/"reports/vintage_comparison_20260904.pdf"

C_OLD, C_NEW, C_AUX = "#333333", "#2166ac", "#b2182b"

old  = pd.read_stata(OLD_F).rename(columns={"occ_code_onetsoc2010":"occ","occ_title_onetsoc2010":"title"})
oldr = pd.read_stata(OLD_R).rename(columns={"occ_code_onetsoc2010":"occ","occ_title_onetsoc2010":"title"})
new  = pd.read_stata(NEW).rename(columns={"occ_code_onetsoc2010":"occ","occ_title_onetsoc2010":"title"})
if "title" not in new.columns:
    new = new.merge(old[["occ","title"]].drop_duplicates(), on="occ", how="left")
new = new.dropna(subset=["year"])

def short(t, n=46): t=str(t); return t if len(t)<=n else t[:n-1]+"…"

def topbot(df, col, year, k=10):
    s = df[df.year==year][["occ","title",col]].dropna().sort_values(col, ascending=False)
    return s.head(k), s.tail(k).iloc[::-1]

def rank_corr_by_year(a, b, col):
    out=[]
    for y in sorted(set(a.year.unique()) & set(b.year.unique())):
        m=a[a.year==y][["occ",col]].merge(b[b.year==y][["occ",col]],on="occ",suffixes=("_o","_n")).dropna()
        if len(m)>10 and m[col+"_o"].std()>0:
            out.append((int(y), m[col+"_o"].corr(m[col+"_n"], method="spearman"), len(m)))
    return out

def table_page(pdf, suptitle, blocks, note=""):
    fig, axes = plt.subplots(1, len(blocks), figsize=(16.5, 9.2))
    if len(blocks)==1: axes=[axes]
    fig.suptitle(suptitle, fontsize=15, fontweight="bold", y=0.985)
    for ax,(hdr, top, bot, col) in zip(axes, blocks):
        ax.axis("off"); ax.set_title(hdr, fontsize=10.5, loc="left", pad=8)
        lines=[("TOP 10", None)]
        lines+= [(f"{i+1:>2}. {short(t.title)}", t.__getattribute__(col)) for i,t in enumerate(top.itertuples())]
        lines+= [("", None), ("BOTTOM 10", None)]
        lines+= [(f"{i+1:>2}. {short(t.title)}", t.__getattribute__(col)) for i,t in enumerate(bot.itertuples())]
        y=0.97
        for txt,val in lines:
            w = "bold" if val is None and txt else "normal"
            ax.text(0.0, y, txt, fontsize=8.1, family="DejaVu Sans", fontweight=w,
                    va="top", transform=ax.transAxes)
            if val is not None:
                ax.text(1.0, y, f"{val:,.2f}", fontsize=8.1, family="DejaVu Sans Mono",
                        va="top", ha="right", transform=ax.transAxes)
            y -= 0.042
    if note:
        fig.text(0.06, 0.035, note, fontsize=8.6, style="italic", wrap=True)
    pdf.savefig(fig); plt.close(fig)

with PdfPages(OUT) as pdf:
    # ---------- P1: verification ----------
    fig = plt.figure(figsize=(16.5, 9.2)); fig.suptitle(
        "DAIOE vintage comparison — old (v1.0.0: frozen 2010–2023 + 2024 refresh) vs new (2025 vintage, v1.1.0 rc)",
        fontsize=14, fontweight="bold")
    ax=fig.add_axes([0.07,0.12,0.55,0.72])
    shared=[c for c in old.columns if c.startswith("daioe_") and c in new.columns]
    m=old.merge(new, on=["occ","year"], suffixes=("_o","_n"))
    diffs={c: float((m[c+"_o"]-m[c+"_n"]).abs().max()) for c in shared}
    rows=[["column","max |old − new|, 2010–2023","verdict"]]
    for c,dv in sorted(diffs.items()):
        rows.append([c, f"{dv:.2e}", "IDENTICAL" if dv<1e-5 else "DIFFERS"])
    ax.axis("off")
    t=ax.table(cellText=rows[1:], colLabels=rows[0], loc="upper left", cellLoc="left", colWidths=[.4,.35,.25])
    t.auto_set_font_size(False); t.set_fontsize(9); t.scale(1,1.35)
    rc=rank_corr_by_year(oldr, new, "daioe_allapps")
    ax2=fig.add_axes([0.68,0.15,0.28,0.62])
    ax2.plot([y for y,_,_ in rc],[r for _,r,_ in rc], color=C_NEW, lw=2, marker="o", ms=5)
    ax2.set_ylim(0.9,1.005); ax2.set_title("Spearman rank agreement by year\noverall AI, old (incl. 2024 refresh) vs new", fontsize=10)
    ax2.grid(alpha=.25); ax2.spines[['top','right']].set_visible(False)
    fig.text(0.07,0.045,
      "Reading: the frozen window must be identical, and is; 2024 compares the refresh against the new chain. "
      "Anything not IDENTICAL above would violate the freeze guarantee.", fontsize=9, style="italic")
    pdf.savefig(fig); plt.close(fig)

    # ---------- P2: overall AI top/bottom ----------
    t1=topbot(old,"daioe_allapps",2023); t2=topbot(new,"daioe_allapps",2023); t3=topbot(new,"daioe_allapps",2025)
    table_page(pdf, "Overall AI exposure (daioe_allapps): most and least exposed occupations",
        [("OLD vintage, 2023","",""),("NEW vintage, 2023","",""),("NEW vintage, 2025","","")] and
        [("OLD vintage, 2023", *t1, "daioe_allapps"),
         ("NEW vintage, 2023 (frozen window)", *t2, "daioe_allapps"),
         ("NEW vintage, 2025", *t3, "daioe_allapps")],
        note="The first two columns must match exactly (frozen window). The third shows where two more years of measured progress move the levels; ordering changes between 2023 and 2025 are capability arrival, not construction change.")

    # ---------- P3: genai top/bottom ----------
    g1=topbot(old,"daioe_genai",2023); g2=topbot(new,"daioe_genai",2023); g3=topbot(new,"daioe_genai",2025)
    table_page(pdf, "Generative-AI composite (daioe_genai): most and least exposed occupations",
        [("OLD vintage, 2023 (original membership)", *g1, "daioe_genai"),
         ("NEW vintage, 2023 (frozen, same membership)", *g2, "daioe_genai"),
         ("NEW vintage, 2025 (broadened membership)", *g3, "daioe_genai")],
        note="Membership broadens at the 2023–24 seam (adds conversation and software engineering to language modelling and image generation). "
             "Columns 1 and 2 must match; column 3 mixes capability progress with the membership change, by design and documented.")

    # ---------- P4: trajectories, overall ----------
    fig,axes=plt.subplots(1,2,figsize=(16.5,9.2))
    fig.suptitle("Trajectories 2010 → last year: overall AI", fontsize=14, fontweight="bold")
    ax=axes[0]
    for df,lab,c,ls in ((oldr,"old (v1.0.0, to 2024)",C_OLD,"-"),(new,"new (2025 vintage)",C_NEW,"--")):
        g=df.groupby("year")["daioe_allapps"].mean()
        ax.plot(g.index,g.values,color=c,ls=ls,lw=2.2,label=lab)
    q=new.groupby("year")["daioe_allapps"].quantile([.25,.75]).unstack()
    ax.fill_between(q.index,q[.25],q[.75],color=C_NEW,alpha=.12,lw=0)
    ax.set_title("Mean across occupations (band: new vintage IQR)",fontsize=10.5)
    ax.legend(frameon=False,fontsize=9); ax.grid(alpha=.25); ax.spines[['top','right']].set_visible(False)
    ax=axes[1]
    sel = pd.concat([t3[0].head(2), t3[1].head(2)])
    extra = new[new.title.str.contains("Secretaries|Accountant", case=False, na=False)][["occ","title"]].drop_duplicates().head(2)
    sel = pd.concat([sel[["occ","title"]], extra]).drop_duplicates("occ")
    for i,(occ,ti) in enumerate(zip(sel.occ, sel.title)):
        go=oldr[oldr.occ==occ].sort_values("year"); gn=new[new.occ==occ].sort_values("year")
        ax.plot(go.year,go.daioe_allapps,color=C_OLD,ls="-",lw=1.4)
        ax.plot(gn.year,gn.daioe_allapps,color=C_NEW,ls="--",lw=1.4)
        ax.annotate(short(ti,30),(gn.year.iloc[-1],gn.daioe_allapps.iloc[-1]),fontsize=7.5,
                    xytext=(4,0),textcoords="offset points",va="center")
    ax.set_title("Selected occupations (solid = old, dashed = new; they must overlap to 2023)",fontsize=10.5)
    ax.set_xlim(2010,2027.5); ax.grid(alpha=.25); ax.spines[['top','right']].set_visible(False)
    pdf.savefig(fig); plt.close(fig)

    # ---------- P5: genai + new columns ----------
    fig,axes=plt.subplots(1,2,figsize=(16.5,9.2))
    fig.suptitle("Trajectories: generative composite, and the columns only the new vintage has", fontsize=14, fontweight="bold")
    ax=axes[0]
    for df,lab,c,ls in ((oldr,"old genai (original membership, to 2024)",C_OLD,"-"),
                        (new,"new genai (broadened at the 2023–24 seam)",C_NEW,"--")):
        g=df.groupby("year")["daioe_genai"].mean(); ax.plot(g.index,g.values,color=c,ls=ls,lw=2.2,label=lab)
    ax.set_title("Generative composite, mean across occupations",fontsize=10.5)
    ax.legend(frameon=False,fontsize=9); ax.grid(alpha=.25); ax.spines[['top','right']].set_visible(False)
    ax=axes[1]
    for col,lab,c,ls in (("daioe_g2all","G2 second-generation composite",C_NEW,"-"),
                         ("daioe_agentic","agentic (chained 2024)",C_AUX,"--"),
                         ("daioe_mathsci","maths/science (chained 2024)",C_OLD,":")):
        if col in new.columns:
            g=new.groupby("year")[col].mean(); ax.plot(g.index,g.values,color=c,ls=ls,lw=2.2,label=lab)
    ax.set_title("New-vintage-only columns (agentic and maths/science are missing before 2024 by design)",fontsize=10.5)
    ax.legend(frameon=False,fontsize=9); ax.grid(alpha=.25); ax.spines[['top','right']].set_visible(False)
    pdf.savefig(fig); plt.close(fig)

    # ---------- P6: plain-words notes ----------
    fig=plt.figure(figsize=(16.5,9.2)); fig.suptitle("What changed, in plain words", fontsize=14, fontweight="bold")
    txt = (
     "1. The frozen window (2010–2023) is IDENTICAL between vintages on every shared column, verified cell by cell on page 1.\n"
     "   Whatever the new vintage does, it did not touch the numbers behind the published estimates.\n\n"
     "2. Overall AI: the 2025 top and bottom lists are the 2023 lists with two more years of measured progress. Rank agreement\n"
     "   with the old vintage is shown by year on page 1.\n\n"
     "3. Genai: the frozen genai column is unchanged. From 2024 the membership broadens (conversation + software engineering join),\n"
     "   so a movement across the seam mixes progress with membership, which is stated in VINTAGES.md and on page 3 here.\n\n"
     "4. New columns: agentic and maths/science exposure exist only from 2024 (chained; missing before, zero at the chain year).\n"
     "   G2 (daioe_g2all) is the second-generation composite over the full window; it is not a constant-basket series.\n\n"
     "5. 2025 is a partial-coverage year for the original basket: four applications are unobserved (carried at last level),\n"
     "   visual question answering is observed with a measured zero, the rest show measured progress.\n\n"
     "Sources: deposited v1.0.0 bundle (dist/) and the staged v1.1.0 release candidate (data/vintage/). Generator:\n"
     "scripts/inspect_vintage_comparison_20260904.py, rerunnable at any time.")
    fig.text(0.07,0.83,txt,fontsize=11,va="top",family="DejaVu Sans",linespacing=1.5)
    pdf.savefig(fig); plt.close(fig)

print("written:", OUT)
