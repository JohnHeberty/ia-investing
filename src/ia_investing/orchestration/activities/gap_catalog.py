"""Canonical gap code catalog for candidate source discovery.

Maps each source kind to the exact gap codes used in the candidate
gap table.  This catalog replaces free interpolation (``source_{kind}_missing``)
with a single source of truth so that ``resolved_gap_codes`` always
matches the codes stored during discovery.
"""

from __future__ import annotations

CANONICAL_GAP_CODES: dict[str, tuple[str, ...]] = {
    "investor_relations": ("investor_relations_missing",),
    "results_page": ("results_page_missing",),
    "cvm_filings": ("cvm_filings_missing",),
    "b3_listing": ("b3_listing_missing",),
}
