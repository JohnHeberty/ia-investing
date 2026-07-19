import pytest

from ia_investing.application.reviews import canonical_hash, ensure_segregation


def test_assessment_hash_is_order_independent() -> None:
    assert canonical_hash({"a": 1, "b": 2}) == canonical_hash({"b": 2, "a": 1})


def test_author_cannot_approve_own_assessment() -> None:
    with pytest.raises(ValueError, match="own work"):
        ensure_segregation("analyst-1", "analyst-1")


def test_distinct_reviewer_is_allowed() -> None:
    ensure_segregation("analyst-1", "reviewer-1")
