"""The series registry: which external series feeds which DAIOE metric, and on what terms.

This is the machine-readable form of the admission rule in
``notes/ADMISSION-rule-metrics-and-subdomains_2026-08-07.md``. Every field it requires is
required here, and a spec missing any of them is refused rather than defaulted.

The six requirements, and why each is fatal rather than cosmetic:

1. ``scale``      keyed on the metric downstream; an unknown one yields NaN with no error path.
2. ``anchor``     the human or reference-floor value; without it the capability transform
                  cannot place the series, and a saturated benchmark cannot be recognised.
3. direction      inherited from the scale family, asserted by test rather than assumed. This
                  is the one the frozen construction gets wrong in its ``threshold`` column.
4. ``date_col``   publication or evaluation dates only. Upload timestamps were the decisive
                  failure of the Hugging Face route and are not accepted.
5. ``protocol``   pure_model or system_level, never mixed within a series. Mixing is what
                  refuted HumanEval's archived tail.
6. ``licence``    must be clean for redistribution in a derived index.

A registry entry is a claim about an external series that someone has checked. It is not a
guess, and `source_note` exists so the checker can say what they checked.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

SCALES = {
    "Percentage correct", "Percentage error", "FID", "BLEU score",
    "Score", "ELO rating", "Perplexity", "Model Entropy",
}
PROTOCOLS = {"pure_model", "system_level"}
# Licences under which a derived index may be redistributed. Verified in track-b-anchor-
# assignments.md §4; CC BY-NC is fine academically but flagged, and CC BY-ND cannot enter at all.
CLEAN_LICENCES = {"CC BY 4.0", "CC BY-SA 4.0", "Apache-2.0", "CC0", "MIT"}


@dataclass(frozen=True)
class SeriesSpec:
    """One external series, declared well enough to be admitted."""

    metrics_name: str          # the DAIOE metric it feeds (existing, or new via Track B)
    parent_name: str           # the DAIOE application
    source: str                # adapter key, e.g. "epoch"
    source_series: str         # the source's own identifier, e.g. "gpqa_diamond"
    score_col: str             # column carrying the value
    date_col: str              # column carrying a publication or evaluation date
    scale: str
    anchor: float
    anchor_kind: str           # human | human-expert | reference-floor | reference-floor-imputed
    protocol: str
    licence: str
    value_multiplier: float = 1.0   # e.g. 100.0 to bring a 0-1 proportion onto a 0-100 scale
    source_note: str = ""

    def validate(self) -> None:
        if self.scale not in SCALES:
            raise ValueError(
                f"{self.metrics_name}: scale {self.scale!r} is not one of the eight declared "
                f"families. Add the transform to _rescale AND _theta explicitly, or the metric "
                f"contributes NaN silently."
            )
        if self.protocol not in PROTOCOLS:
            raise ValueError(f"{self.metrics_name}: protocol must be one of {sorted(PROTOCOLS)}")
        if self.licence not in CLEAN_LICENCES:
            raise ValueError(
                f"{self.metrics_name}: licence {self.licence!r} is not cleared for "
                f"redistribution in a derived index. Resolve it before ingestion."
            )
        if not (self.anchor == self.anchor) or self.anchor is None:   # NaN check
            raise ValueError(f"{self.metrics_name}: an anchor is required, see the admission rule")
        if self.anchor_kind not in {
            "human", "human-expert", "human-ceiling", "reference-floor", "reference-floor-imputed"
        }:
            raise ValueError(f"{self.metrics_name}: anchor_kind {self.anchor_kind!r} not recognised")
        if not self.source_note:
            raise ValueError(
                f"{self.metrics_name}: source_note is required. A registry entry is a claim "
                f"someone checked; record what was checked."
            )


def load_registry(path: Path) -> list[SeriesSpec]:
    """Read and validate a registry file. Raises on the first bad entry."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    specs = [SeriesSpec(**row) for row in raw]
    seen: set[str] = set()
    for s in specs:
        s.validate()
        if s.metrics_name in seen:
            raise ValueError(f"{s.metrics_name}: declared twice; one series per metric")
        seen.add(s.metrics_name)
    return specs
