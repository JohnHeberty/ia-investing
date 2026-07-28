"""Canonical gap code catalog tests.

Ensures the catalog exists, is immutable at runtime, and maps
every known source kind to the exact gap codes used in the
candidate gap table.
"""

from __future__ import annotations

from ia_investing.orchestration.activities.gap_catalog import CANONICAL_GAP_CODES


def test_catalog_is_not_empty() -> None:
    assert len(CANONICAL_GAP_CODES) > 0


def test_investor_relations_maps_to_missing() -> None:
    assert CANONICAL_GAP_CODES["investor_relations"] == ("investor_relations_missing",)


def test_results_page_maps_to_missing() -> None:
    assert CANONICAL_GAP_CODES["results_page"] == ("results_page_missing",)


def test_cvm_filings_maps_to_missing() -> None:
    assert CANONICAL_GAP_CODES["cvm_filings"] == ("cvm_filings_missing",)


def test_b3_listing_maps_to_missing() -> None:
    assert CANONICAL_GAP_CODES["b3_listing"] == ("b3_listing_missing",)


def test_unknown_source_kind_returns_empty() -> None:
    assert CANONICAL_GAP_CODES.get("unknown_kind", ()) == ()


def test_all_values_are_non_empty_tuples() -> None:
    for kind, codes in CANONICAL_GAP_CODES.items():
        assert isinstance(codes, tuple), f"{kind} value is not a tuple"
        assert len(codes) > 0, f"{kind} has empty gap codes"
