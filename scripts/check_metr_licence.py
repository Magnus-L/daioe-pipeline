#!/usr/bin/env python3
"""Has METR added the CC BY 4.0 licence to eval-analysis-public yet?

METR committed to this on 18 Aug 2026 ("we will add a CC-BY-4.0 license to
eval-analysis-public soon"), in reply to our asking. It matters because it changes the BASIS
of our agentic series, not our right to use it: today we rely on a permission granted to the
AI-Econ Lab, which does not travel with the data, so anyone replicating or extending our work
lands on the same question we did. A licence file fixes that for everyone.

Encoded rather than remembered, because "check whether the upstream licence landed" is exactly
the kind of task that is never done. Run it before any vintage that ships METR-derived values.

    .venv/bin/python scripts/check_metr_licence.py

WHEN IT FLIPS TO CC BY 4.0, four things change:
  1. notes/PERMISSION-metr_2026-08-13.md    record the date; the basis upgrades
  2. LICENSE-DATA                           METR moves from "cleared but not yet ingested"
                                            into the upstream inheritance table
  3. data/updates/provenance_metr_*.json    licence: null -> "CC BY 4.0"
  4. src/daioe/providers/registry.py        METR becomes registry-eligible; CLEAN_LICENCES
                                            already accepts CC BY 4.0, so the series could
                                            move to the adapter route if we ever want it
"""
from __future__ import annotations

import json
import sys
import urllib.request

REPO = "METR/eval-analysis-public"
UA = "AI-Econ Lab research (mlodefalk@gmail.com)"
EXPECTED = "cc-by-4.0"


def _get(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


def headroom() -> None:
    """Frontier-to-ceiling distance on both reliability bars, so suite exhaustion is
    watched, not discovered (added 24 Aug 2026, the day the 50% bar's 2026 readings
    crossed the 960-minute bound and the series moved to the 80% bar). Reads METR's
    current published file; falls back to the pinned local copy if unreachable."""
    import io
    from pathlib import Path

    import yaml

    ceiling = 960.0
    status, body = _get("https://metr.org/assets/benchmark_results_1_1.yaml")
    src = "metr.org (live)"
    if status != 200:
        body = (Path(__file__).resolve().parents[1]
                / "data/updates/metr_20260813/benchmark_results_1_1.yaml").read_bytes()
        src = "pinned local copy (metr.org unreachable)"
    doc = yaml.safe_load(io.BytesIO(body))
    for bar, field in (("50%", "p50_horizon_length"), ("80% (ACTIVE)", "p80_horizon_length")):
        top = max(float(m["metrics"][field]["estimate"]) for m in doc["results"].values())
        note = ""
        if top > ceiling:
            note = "  ** SUITE EXHAUSTED on this bar **"
        elif top > ceiling / 2:
            note = "  ** WARNING: past half the ceiling; plan the successor now **"
        print(f"headroom     {bar:>12} bar: frontier {top:8.1f} of {ceiling:.0f} min{note}")
    print(f"             (source: {src})")


def main() -> int:
    headroom()
    status, body = _get(f"https://api.github.com/repos/{REPO}")
    if status != 200:
        print(f"github api returned {status}; cannot tell")
        return 2
    meta = json.loads(body)
    lic = meta.get("license")
    files = {f: _get(f"https://raw.githubusercontent.com/{REPO}/main/{f}")[0]
             for f in ("LICENSE", "LICENSE.md", "LICENSE.txt")}
    present = [f for f, c in files.items() if c == 200]

    print(f"repo         {REPO}")
    print(f"pushed_at    {meta.get('pushed_at')}")
    print(f"api licence  {lic.get('spdx_id') if lic else None}")
    print(f"licence file {present or 'none of LICENSE, LICENSE.md, LICENSE.txt'}")

    if lic and str(lic.get("key", "")).lower() == EXPECTED:
        print("\nLANDED. METR now carries CC BY 4.0. Update the four places listed in this "
              "file's docstring; the permission-to-us stops being the binding basis.")
        return 0
    if lic or present:
        print(f"\nCHANGED but not to {EXPECTED}. Read it before assuming anything.")
        return 1
    print("\nNot yet. Committed by METR on 18 Aug 2026, not in place. Our basis remains the "
          "written permission of 13 Aug, which does not travel downstream. Nothing of ours "
          "waits on it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
