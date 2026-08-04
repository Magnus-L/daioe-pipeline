"""Preflight: check every input the pipeline needs, before spending a run on finding out.

Two audiences, one tool.

For us: `data/reference` and `data/enriched_ref` currently point into
`~/Downloads/DAIOE 20260527/`, which no longer exists. Every stage still BUILDS, so
`run_all.py --no-validate` completes and looks healthy; validation then dies on the
first missing target, one file at a time, ten minutes into a session. This prints the
whole list at once so a restore can be verified complete before anything is run.

For external users of the release: the pipeline reads twenty-odd files across four
directories, three of which are symlinks into a source tree we cannot ship. Telling
someone their data layout is wrong is worth more than a traceback from stage 1.

The list is derived from the source rather than maintained by hand: static
`raw_file("...")` / `enriched_ref_file("...")` literals are parsed out of `src/`,
the crosswalks come from the active config, and the two dynamic reference families in
stage 5 are expanded from the config's taxonomy list.

Usage:  .venv/bin/python scripts/preflight.py [--config config.yaml]
Exit 0 if everything a build needs is present; 1 otherwise. Validation-only inputs are
reported but do not set the exit code, since `--no-validate` remains usable without them.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

CALL = re.compile(r"(raw_file|reference_file|enriched_ref_file)\(\s*\"([^\"]+)\"")

# Which helper feeds which config path key, and whether a build can proceed without it.
KIND = {
    "raw_file": ("raw", True),
    "enriched_ref_file": ("enriched_ref", False),
    "reference_file": ("reference", False),
}


def static_literals() -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for py in SRC.rglob("*.py"):
        for helper, name in CALL.findall(py.read_text(encoding="utf-8")):
            found.add((helper, name))
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / args.config).read_text(encoding="utf-8"))
    paths = cfg["paths"] if "paths" in cfg else cfg.get("raw", {}).get("paths", {})
    if not paths:
        # config.py resolves cfg.raw["paths"]; mirror whichever layout this file uses.
        paths = {k: v for k, v in cfg.items() if k in ("raw", "reference", "enriched_ref", "out", "reports")}

    wanted: set[tuple[str, str]] = static_literals()

    # crosswalks named in the active config, read through raw_file by stage 5
    for tax, spec in (cfg.get("taxonomies") or {}).items():
        if isinstance(spec, dict) and spec.get("crosswalk"):
            wanted.add(("raw_file", spec["crosswalk"]))

    # stage 5's two dynamic reference families, one per configured taxonomy
    for tax in (cfg.get("taxonomies") or {}):
        wanted.add(("reference_file", f"daioe_panel_{tax}.dta"))
        wanted.add(("reference_file", f"Publication/daioe_{tax}.dta"))

    print(f"config: {args.config}\n")
    missing_build = missing_val = 0
    for kind in ("raw_file", "enriched_ref_file", "reference_file"):
        key, build_critical = KIND[kind]
        base_rel = paths.get(key)
        base = (ROOT / base_rel).resolve() if base_rel else None
        names = sorted(n for k, n in wanted if k == kind)
        if not names:
            continue
        label = "BUILD" if build_critical else "validation only"
        print(f"=== {key}  ({label}) ===")
        if base is None:
            print("  no path configured\n")
            continue
        if not base.exists():
            print(f"  DIRECTORY MISSING: {base_rel}")
            link = ROOT / base_rel
            if link.is_symlink():
                print(f"    symlink -> {link.readlink()}")
            print(f"    {len(names)} files unreachable\n")
            if build_critical:
                missing_build += len(names)
            else:
                missing_val += len(names)
            continue
        for n in names:
            ok = (base / n).exists()
            if not ok:
                if build_critical:
                    missing_build += 1
                else:
                    missing_val += 1
            print(f"  {'ok  ' if ok else 'MISS'}  {n}")
        print()

    print(f"build-critical inputs missing : {missing_build}")
    print(f"validation-only inputs missing: {missing_val}")
    if missing_build == 0 and missing_val == 0:
        print("\nall inputs present; run_all.py should complete with validation")
    elif missing_build == 0:
        print("\nbuild is runnable (`run_all.py --no-validate`); validation is not")
    return 1 if missing_build else 0


if __name__ == "__main__":
    sys.exit(main())
