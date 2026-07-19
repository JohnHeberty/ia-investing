from decimal import Decimal

import pytest

from ia_investing.application.metrics import calculate_known_metric


def test_known_metric_uses_decimal_without_float_loss() -> None:
    result = calculate_known_metric(
        "current_ratio", {"current_assets": Decimal("10.00"), "current_liabilities": Decimal("4.00")}
    )
    assert result == Decimal("2.5")


def test_metric_fails_closed_on_zero_denominator() -> None:
    with pytest.raises(ValueError, match="denominator"):
        calculate_known_metric("net_margin", {"net_income": Decimal("1"), "revenue": Decimal("0")})
