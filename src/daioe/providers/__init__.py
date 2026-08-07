"""Source adapters for the annual refresh (Track B, phase B2).

Each adapter turns one external benchmark source into rows in the update-workbook schema
that ``stage2_ai_progress._load_updates`` already validates, so ingestion keeps a single
gate rather than one per source.

The division of labour is deliberate and is the thing to preserve:

* the **adapter** knows how to read a source, find its score and date columns, and build a
  dated frontier;
* the **registry** (`registry.py`) knows which external series feeds which DAIOE metric, and
  carries the six fields the admission rule requires;
* the **loader** in stage 2 is the only thing that may write into the measures sheet, and it
  refuses anything it does not recognise.

An adapter that cannot satisfy the registry's declarations raises. Nothing passes silently:
an unknown scale would produce ``NaN`` value_scaled with no error path, which is exactly the
failure the guards exist to prevent.
"""
from __future__ import annotations

from .registry import SeriesSpec, load_registry  # noqa: F401
