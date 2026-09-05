"""Ship a SSYK code-title lookup so top-N lists have names and joins have keys.

The frozen SSYK panels store the occupation key as a Stata category whose label
fuses code and title ("0110 Officerare"); the refresh panels store the code
numerically, which drops leading zeros. This lookup gives every user canonical
zero-padded string codes with Swedish titles, extracted from the frozen panels'
own value labels. Ships in the bundle as occupation_titles_ssyk.csv.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
rows = []
for tx, key in [("ssyk2012", "ssyk2012_4"), ("ssyk96", "ssyk96_4")]:
    d = pd.read_stata(ROOT / "data/reference/Publication" / f"daioe_{tx}.dta")
    for lab in d[key].astype(str).unique():
        lab = lab.strip()
        code, _, title = lab.partition(" ")
        code = code.split(".")[0].zfill(4)
        if title:
            rows.append({"taxonomy": tx, "code": code, "title": title})
out = pd.DataFrame(rows).drop_duplicates(["taxonomy", "code"]).sort_values(["taxonomy", "code"])
p = ROOT / "data/derived/occupation_titles_ssyk.csv"
out.to_csv(p, index=False)
print(f"{p.name}: {len(out)} rows "
      f"({(out.taxonomy=='ssyk2012').sum()} SSYK 2012, {(out.taxonomy=='ssyk96').sum()} SSYK 96)")
