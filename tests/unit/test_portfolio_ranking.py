from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from ia_investing.domain.portfolio_ranking import (
    PortfolioRankingInput,
    PortfolioStage,
    RankingPolicy,
    evaluate_portfolio,
    rank_portfolios,
)

NOW = datetime(2026, 7, 21, 12, tzinfo=UTC)
COMPONENTS = {
    "excess_return": Decimal("0.80"),
    "sortino": Decimal("0.70"),
    "drawdown_control": Decimal("0.75"),
    "regime_stability": Decimal("0.65"),
    "walk_forward_robustness": Decimal("0.70"),
    "risk_compliance": Decimal("1.00"),
    "thesis_health": Decimal("0.90"),
    "cost_capacity": Decimal("0.80"),
    "data_model_confidence": Decimal("0.90"),
}


def portfolio(**overrides):
    values = {
        "portfolio_id": "p1",
        "name": "Quality BR",
        "category": "quality",
        "benchmark": "IBOV",
        "currency": "BRL",
        "risk_class": "moderate",
        "environment": "paper",
        "stage": PortfolioStage.PAPER_LIVE,
        "inception_at": NOW - timedelta(days=365),
        "data_as_of": NOW - timedelta(hours=2),
        "nav_reconciled": True,
        "backtest_point_in_time_verified": True,
        "approved_version": True,
        "open_hard_breaches": 0,
        "open_soft_breaches": 0,
        "expired_theses": 0,
        "thesis_coverage": Decimal("0.95"),
        "data_confidence": Decimal("0.95"),
        "low_liquidity": False,
        "high_turnover": False,
        "components": COMPONENTS,
    }
    values.update(overrides)
    return PortfolioRankingInput(**values)


def test_eligible_portfolio_receives_deterministic_score():
    result = evaluate_portfolio(portfolio(), RankingPolicy(), now=NOW)
    assert result.eligible is True
    assert result.score == Decimal("0.7875")
    assert result.penalty == Decimal("0.0000")


def test_hard_breach_blocks_ranking_instead_of_merely_reducing_score():
    result = evaluate_portfolio(portfolio(open_hard_breaches=1), RankingPolicy(), now=NOW)
    assert result.eligible is False
    assert result.score is None
    assert "open_hard_risk_breach" in result.reasons


def test_stale_data_is_visible_as_penalty():
    result = evaluate_portfolio(
        portfolio(data_as_of=NOW - timedelta(days=3)),
        RankingPolicy(),
        now=NOW,
    )
    assert result.eligible is True
    assert result.penalty == Decimal("0.1500")
    assert result.score == Decimal("0.6375")


def test_portfolios_only_compete_inside_same_cohort():
    results = rank_portfolios(
        [
            portfolio(portfolio_id="quality-a"),
            portfolio(portfolio_id="quality-b", components={**COMPONENTS, "excess_return": Decimal("0.95")}),
            portfolio(portfolio_id="value-a", category="value"),
        ],
        now=NOW,
    )
    ranked = {result.portfolio_id: result for result in results}
    assert ranked["quality-b"].rank == 1
    assert ranked["quality-a"].rank == 2
    assert ranked["value-a"].rank == 1


def test_missing_component_fails_closed():
    incomplete = dict(COMPONENTS)
    incomplete.pop("sortino")
    result = evaluate_portfolio(portfolio(components=incomplete), RankingPolicy(), now=NOW)
    assert result.eligible is False
    assert result.reasons == ("missing_components:sortino",)


def test_invalid_component_is_rejected():
    invalid = dict(COMPONENTS)
    invalid["sortino"] = Decimal("1.1")
    with pytest.raises(ValueError, match="between 0 and 1"):
        evaluate_portfolio(portfolio(components=invalid), RankingPolicy(), now=NOW)


def test_future_data_is_not_ranked():
    result = evaluate_portfolio(
        portfolio(data_as_of=NOW + timedelta(minutes=1)),
        RankingPolicy(),
        now=NOW,
    )
    assert result.eligible is False
    assert "data_as_of_in_future" in result.reasons


def test_naive_timestamps_are_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate_portfolio(
            portfolio(data_as_of=datetime(2026, 7, 21, 10, 0)),
            RankingPolicy(),
            now=NOW,
        )
