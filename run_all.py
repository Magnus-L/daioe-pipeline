#!/usr/bin/env python3
"""Entry point: run the DAIOE pipeline end to end and write a validation report.

    python run_all.py [--config config.yaml] [--stages 1,2,3,4,5] [--no-validate]

Each stage returns its primary DataFrame(s) and writes checkpoints to data/out so a
later stage (or a fresh process) can consume them. Validation compares every produced
panel against the Stata ground truth and writes reports/validation_<ts>.md.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# make src/ importable without an editable install
SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from daioe.config import load_config  # noqa: E402
from daioe import validate as V  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the DAIOE pipeline.")
    ap.add_argument("--config", default=None, help="path to config.yaml")
    ap.add_argument("--stages", default="1,2,3,4,5", help="comma list of stages to run")
    ap.add_argument("--no-validate", action="store_true", help="skip validation")
    args = ap.parse_args()

    cfg = load_config(args.config)
    stages = {s.strip() for s in args.stages.split(",") if s.strip()}
    results: list[V.CompareResult] = []

    # Stage imports are deferred so partial scaffolds still import run_all.
    if "1" in stages:
        from daioe import stage1_onet
        results += stage1_onet.run(cfg, validate=not args.no_validate)
    if "2" in stages:
        from daioe import stage2_ai_progress
        results += stage2_ai_progress.run(cfg, validate=not args.no_validate)
    if "3" in stages:
        from daioe import stage3_mapping
        results += stage3_mapping.run(cfg, validate=not args.no_validate)
    if "4" in stages:
        from daioe import stage4_index
        results += stage4_index.run(cfg, validate=not args.no_validate)
    if "5" in stages:
        from daioe import stage5_taxonomies
        results += stage5_taxonomies.run(cfg, validate=not args.no_validate)

    if results and not args.no_validate:
        report = V.write_report(results, cfg.path("reports"))
        n_pass = sum(r.passed for r in results)
        print(f"\n{n_pass}/{len(results)} targets passed. Report: {report}")
        return 0 if n_pass == len(results) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
