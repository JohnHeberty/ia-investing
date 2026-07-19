from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ia_investing.application.financial_facts import require_aware, validate_fact_value


@pytest.mark.parametrize("status", ["reported", "calculated"])
def test_value_carrying_status_requires_decimal(status: str) -> None:
    validate_fact_value(Decimal("0"), status)
    with pytest.raises(ValueError, match="inconsistent"):
        validate_fact_value(None, status)


@pytest.mark.parametrize("status", ["missing", "not_applicable", "parse_error", "suppressed"])
def test_non_value_status_forbids_synthetic_zero(status: str) -> None:
    validate_fact_value(None, status)
    with pytest.raises(ValueError, match="inconsistent"):
        validate_fact_value(Decimal("0"), status)


def test_as_of_must_be_timezone_aware() -> None:
    require_aware(datetime(2026, 7, 18, tzinfo=UTC), "as_of")
    with pytest.raises(ValueError, match="timezone"):
        require_aware(datetime(2026, 7, 18), "as_of")
