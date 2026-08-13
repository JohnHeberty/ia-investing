"""Unit tests for ia_investing.domain.valuation — DCF and valuation models."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ia_investing.domain.valuation import (
    DCFInput,
    DCFResult,
    discounted_cash_flow,
    relative_valuation,
    reverse_dcf_growth,
    weighted_scenarios,
)


@pytest.mark.unit
class TestDCF:
    def test_basic_dcf(self):
        inp = DCFInput(
            free_cash_flows=(Decimal("100"), Decimal("110"), Decimal("121")),
            discount_rate=Decimal("0.10"),
            terminal_growth=Decimal("0.03"),
            net_debt=Decimal("500"),
            shares_outstanding=Decimal("100"),
        )
        result = discounted_cash_flow(inp)
        assert isinstance(result, DCFResult)
        assert result.enterprise_value > 0
        assert result.equity_value < result.enterprise_value
        assert result.value_per_share > 0

    def test_empty_flows_raises(self):
        inp = DCFInput((), Decimal("0.10"), Decimal("0.03"), Decimal("0"), Decimal("100"))
        with pytest.raises(ValueError, match="at least one"):
            discounted_cash_flow(inp)

    def test_rate_not_exceeding_growth_raises(self):
        inp = DCFInput((Decimal("100"),), Decimal("0.03"), Decimal("0.03"), Decimal("0"), Decimal("100"))
        with pytest.raises(ValueError, match="discount rate"):
            discounted_cash_flow(inp)

    def test_zero_shares_raises(self):
        inp = DCFInput((Decimal("100"),), Decimal("0.10"), Decimal("0.03"), Decimal("0"), Decimal("0"))
        with pytest.raises(ValueError, match="shares outstanding"):
            discounted_cash_flow(inp)


@pytest.mark.unit
class TestWeightedScenarios:
    def test_basic(self):
        base = DCFResult(Decimal("1000"), Decimal("500"), Decimal("10"))
        bear = DCFResult(Decimal("800"), Decimal("300"), Decimal("6"))
        bull = DCFResult(Decimal("1200"), Decimal("700"), Decimal("14"))
        probs = {"bear": Decimal("0.25"), "base": Decimal("0.50"), "bull": Decimal("0.25")}
        result = weighted_scenarios({"bear": bear, "base": base, "bull": bull}, probs)
        assert result.enterprise_value == Decimal("1000")
        assert result.equity_value == Decimal("500")
        assert result.value_per_share == Decimal("10")

    def test_missing_scenario_raises(self):
        with pytest.raises(ValueError, match="bear, base and bull"):
            weighted_scenarios({"base": DCFResult(Decimal("1"), Decimal("1"), Decimal("1"))}, {"base": Decimal("1")})

    def test_probs_not_sum_to_one_raises(self):
        base = bull = bear = DCFResult(Decimal("1"), Decimal("1"), Decimal("1"))
        with pytest.raises(ValueError, match="sum to one"):
            weighted_scenarios(
                {"bear": bear, "base": base, "bull": bull},
                {"bear": Decimal("0.5"), "base": Decimal("0.3"), "bull": Decimal("0.1")},
            )


@pytest.mark.unit
class TestRelativeValuation:
    def test_basic(self):
        result = relative_valuation(Decimal("100"), Decimal("5"), Decimal("200"), Decimal("50"))
        assert result.enterprise_value == Decimal("500")
        assert result.equity_value == Decimal("300")
        assert result.value_per_share == Decimal("6")

    def test_negative_metric_raises(self):
        with pytest.raises(ValueError, match="outside"):
            relative_valuation(Decimal("-1"), Decimal("5"), Decimal("0"), Decimal("50"))

    def test_zero_multiple_raises(self):
        with pytest.raises(ValueError, match="outside"):
            relative_valuation(Decimal("100"), Decimal("0"), Decimal("0"), Decimal("50"))


@pytest.mark.unit
class TestReverseDcf:
    def test_basic(self):
        result = reverse_dcf_growth(Decimal("1000"), Decimal("100"), Decimal("0.10"), 5)
        assert isinstance(result, Decimal)
        assert Decimal("-0.50") < result < Decimal("0.10")

    def test_negative_market_value_raises(self):
        with pytest.raises(ValueError, match="positive"):
            reverse_dcf_growth(Decimal("-100"), Decimal("100"), Decimal("0.10"))

    def test_zero_years_raises(self):
        with pytest.raises(ValueError, match="positive"):
            reverse_dcf_growth(Decimal("1000"), Decimal("100"), Decimal("0.10"), 0)
