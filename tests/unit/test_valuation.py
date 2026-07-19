from decimal import Decimal

import pytest

from ia_investing.domain.valuation import (
    DCFInput,
    discounted_cash_flow,
    relative_valuation,
    reverse_dcf_growth,
    weighted_scenarios,
)


def test_dcf_golden_case() -> None:
    result = discounted_cash_flow(
        DCFInput(
            free_cash_flows=(Decimal("100"), Decimal("110"), Decimal("121")),
            discount_rate=Decimal("0.10"),
            terminal_growth=Decimal("0.03"),
            net_debt=Decimal("200"),
            shares_outstanding=Decimal("100"),
        )
    )
    assert result.value_per_share.quantize(Decimal("0.0001")) == Decimal("14.1039")


def test_weighted_scenarios_require_complete_probability_mass() -> None:
    base = discounted_cash_flow(DCFInput((Decimal("100"),), Decimal("0.10"), Decimal("0.02"), Decimal(0), Decimal(1)))
    with pytest.raises(ValueError, match="sum to one"):
        weighted_scenarios(
            {"bear": base, "base": base, "bull": base},
            {"bear": Decimal("0.2"), "base": Decimal("0.5"), "bull": Decimal("0.2")},
        )


def test_relative_and_reverse_dcf_are_deterministic() -> None:
    relative = relative_valuation(Decimal("100"), Decimal("8"), Decimal("200"), Decimal("100"))
    assert relative.value_per_share == Decimal("6")
    growth = reverse_dcf_growth(Decimal("2000"), Decimal("100"), Decimal("0.10"))
    assert Decimal("-0.50") < growth < Decimal("0.10")
