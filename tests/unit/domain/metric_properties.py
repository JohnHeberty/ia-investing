"""Property-based tests for metric formulas and financial identities."""

from decimal import Decimal

import pytest

from ia_investing.application.financial_facts import VALUE_STATUSES, validate_fact_value
from ia_investing.application.metrics import calculate_known_metric


def test_current_ratio_identity() -> None:
    """current_ratio = current_assets / current_liabilities."""
    result = calculate_known_metric(
        "current_ratio",
        {
            "current_assets": Decimal("100"),
            "current_liabilities": Decimal("50"),
        },
    )
    assert result == Decimal("100") / Decimal("50")


def test_current_ratio_inverses() -> None:
    """Doubling both assets and liabilities preserves the ratio."""
    base = calculate_known_metric(
        "current_ratio",
        {
            "current_assets": Decimal("200"),
            "current_liabilities": Decimal("100"),
        },
    )
    doubled = calculate_known_metric(
        "current_ratio",
        {
            "current_assets": Decimal("400"),
            "current_liabilities": Decimal("200"),
        },
    )
    assert base == doubled


def test_net_margin_boundary() -> None:
    """Net margin is zero when net income is zero."""
    result = calculate_known_metric(
        "net_margin",
        {
            "net_income": Decimal("0"),
            "revenue": Decimal("1000"),
        },
    )
    assert result == Decimal("0")


def test_net_margin_one_hundred_percent() -> None:
    """Net margin is 1 when net income equals revenue."""
    result = calculate_known_metric(
        "net_margin",
        {
            "net_income": Decimal("500"),
            "revenue": Decimal("500"),
        },
    )
    assert result == Decimal("1")


def test_debt_to_equity_basic() -> None:
    """debt_to_equity = total_debt / equity."""
    result = calculate_known_metric(
        "debt_to_equity",
        {
            "total_debt": Decimal("300"),
            "equity": Decimal("100"),
        },
    )
    assert result == Decimal("3")


def test_division_by_zero_raises() -> None:
    """Zero denominator raises ValueError."""
    with pytest.raises(ValueError, match="zero"):
        calculate_known_metric(
            "current_ratio",
            {
                "current_assets": Decimal("100"),
                "current_liabilities": Decimal("0"),
            },
        )


def test_unknown_metric_raises() -> None:
    """Unknown metric name raises ValueError."""
    with pytest.raises(ValueError, match="not registered"):
        calculate_known_metric("unknown_metric", {})


# --- validate_fact_value properties ---


def test_value_status_consistency_property() -> None:
    """Value-carrying statuses always require non-None value."""
    for status in ("reported", "calculated"):
        validate_fact_value(Decimal("100"), status)
        with pytest.raises(ValueError):
            validate_fact_value(None, status)


def test_non_value_status_never_allows_value() -> None:
    """Non-value statuses never allow a Decimal value."""
    for status in ("missing", "not_applicable", "parse_error", "suppressed"):
        validate_fact_value(None, status)
        with pytest.raises(ValueError):
            validate_fact_value(Decimal("0"), status)


def test_all_statuses_covered() -> None:
    """VALUE_STATUSES contains exactly the expected set."""
    expected = {"reported", "calculated", "missing", "not_applicable", "parse_error", "suppressed"}
    assert expected == VALUE_STATUSES
