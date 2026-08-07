"""Typed access to config.yaml.

We keep a single config object threaded through every stage so that an annual
refresh (Phase 2) or a new taxonomy (Phase 3) is a config edit, not a code edit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Package root = two levels up from this file (src/daioe/config.py -> package root).
PKG_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    """Immutable view over config.yaml with path resolution."""

    raw: dict[str, Any]
    root: Path

    # --- horizon ---
    @property
    def base_year(self) -> int:
        return int(self.raw["base_year"])

    @property
    def year_final(self) -> int:
        return int(self.raw["year_final"])

    @property
    def years(self) -> range:
        return range(self.base_year, self.year_final + 1)

    # --- construction parameters ---
    @property
    def social_weight(self) -> float:
        return float(self.raw["social_weight"])

    @property
    def conseq_error_weight(self) -> float:
        return float(self.raw["conseq_error_weight"])

    @property
    def apply_conseq_error(self) -> bool:
        return bool(self.raw.get("apply_conseq_error", False))

    @property
    def scale_up(self) -> float:
        return float(self.raw["scale_up"])

    # --- categories / columns ---
    @property
    def app_categories(self) -> list[str]:
        return list(self.raw["app_categories"])

    @property
    def app_categories_publication(self) -> list[str]:
        return list(self.raw["app_categories_publication"])

    @property
    def app_id_membership(self) -> dict[str, list[int]]:
        return {k: list(v) for k, v in self.raw["app_id_membership"].items()}

    @property
    def comparator_cols(self) -> list[str]:
        return list(self.raw["comparator_cols"])

    @property
    def occ_characteristic_cols(self) -> list[str]:
        return list(self.raw["occ_characteristic_cols"])

    @property
    def taxonomies(self) -> dict[str, dict[str, Any]]:
        return dict(self.raw["taxonomies"])

    @property
    def export_formats(self) -> list[str]:
        return list(self.raw["export_formats"])

    # --- tolerances ---
    @property
    def tol_internal(self) -> float:
        return float(self.raw["tol_internal"])

    @property
    def tol_publication(self) -> float:
        return float(self.raw["tol_publication"])

    @property
    def benchmark_updates(self) -> list[Path]:
        """Optional benchmark update workbooks appended to the frozen measures sheet
        (Phase 2 annual refresh; empty list = frozen baseline, bit-exact)."""
        return [(self.root / p).resolve() for p in (self.raw.get("benchmark_updates") or [])]

    @property
    def benchmark_extensions(self) -> list[Path]:
        """Track B extension workbooks: NEW metrics and subdomains (the second door).

        Distinct from ``benchmark_updates``, which is basket-faithful and refuses anything the
        frozen sheet does not know. Each extension workbook carries a ``measures`` and a
        ``metrics`` sheet; the loader's guards are in ``stage2_ai_progress._load_extensions``.
        Empty list = frozen baseline, bit-exact.
        """
        return [(self.root / p).resolve() for p in (self.raw.get("benchmark_extensions") or [])]

    @property
    def frozen_year_final(self) -> int:
        """Last year of the PUBLISHED window, which bounds where an extension may link.

        Distinct from ``year_final``, which moves with each refresh. Freeze-history means no
        extension may alter a value inside the published window, so the earliest admissible
        chain point is this year plus one.
        """
        return int(self.raw.get("frozen_year_final", 2023))

    # --- path resolution ---
    def path(self, key: str) -> Path:
        """Resolve a configured path key (raw, reference, enriched_ref, out, reports)."""
        return (self.root / self.raw["paths"][key]).resolve()

    def raw_file(self, name: str) -> Path:
        return self.path("raw") / name

    def reference_file(self, name: str) -> Path:
        return self.path("reference") / name

    def enriched_ref_file(self, name: str) -> Path:
        return self.path("enriched_ref") / name

    def out_file(self, name: str) -> Path:
        return self.path("out") / name


def load_config(path: str | Path | None = None) -> Config:
    """Load config.yaml (default: package root) into a Config object."""
    cfg_path = Path(path) if path else (PKG_ROOT / "config.yaml")
    with open(cfg_path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return Config(raw=raw, root=PKG_ROOT)
