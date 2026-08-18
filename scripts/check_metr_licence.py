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


def main() -> int:
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
