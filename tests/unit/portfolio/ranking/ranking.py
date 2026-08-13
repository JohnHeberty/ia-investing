"""Unit tests for ia_investing.domain.portfolio_ranking — ranking logic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from ia_investing.domain.portfolio_ranking import (
    ELIGIBLE_STAGES,
    PortfolioRankingInput,
    PortfolioStage,
    RankingPolicy,
    RankingResult,
    cohort_key,
    evaluate_portfolio,
    rank_portfolios,
    top_x,
)


def _make_input(**overrides) -> PortfolioRankingInput:
    defaults = dict(
        portfolio_id="p1",
        name="Test",
        category="equity",
        benchmark="IBOV",
        currency="BRL",
        risk_class="moderate",
        environment="paper",
        stage=PortfolioStage.PAPER_LIVE,
        inception_at=datetime(2025, 1, 1, tzinfo=UTC),
        data_as_of=datetime(2026, 6, 1, tzinfo=UTC),
        nav_reconciled=True,
        backtest_point_in_time_verified=True,
        approved_version=True,
        open_hard_breaches=0,
        open_soft_breaches=0,
        expired_theses=0,
        thesis_coverage=Decimal("0.90"),
        data_confidence=Decimal("0.90"),
        low_liquidity=False,
        high_turnover=False,
        components={k: Decimal("0.8") for k in RankingPolicy().weights},
    )
    defaults.update(overrides)
    return PortfolioRankingInput(**defaults)


@pytest.mark.unit
class TestRankingPolicy:
    def test_default_valid(self):
        p = RankingPolicy()
        assert p.minimum_history_days == 90
        assert sum(p.weights.values()) == Decimal("1")

    def test_invalid_weights_raises(self):
        with pytest.raises(ValueError, match="sum exactly to 1"):
            RankingPolicy(weights={"a": Decimal("0.5"), "b": Decimal("0.6")})

    def test_zero_history_raises(self):
        with pytest.raises(ValueError, match="positive"):
            RankingPolicy(minimum_history_days=0)


@pytest.mark.unit
class TestCohortKey:
    def test_basic(self):
        item = _make_input()
        key = cohort_key(item)
        assert "equity" in key
        assert "IBOV" in key
        assert "BRL" in key

    def test_same_params_same_key(self):
        a = _make_input()
        b = _make_input(portfolio_id="p2")
        assert cohort_key(a) == cohort_key(b)


@pytest.mark.unit
class TestEvaluatePortfolio:
    def test_eligible_portfolio(self):
        item = _make_input()
        result = evaluate_portfolio(item, RankingPolicy())
        assert result.eligible is True
        assert result.score is not None
        assert result.score >= 0

    def test_wrong_stage_not_eligible(self):
        item = _make_input(stage=PortfolioStage.DRAFT)
        result = evaluate_portfolio(item, RankingPolicy())
        assert result.eligible is False
        assert any("stage_not_rankable" in r for r in result.reasons)

    def test_nav_not_reconciled(self):
        item = _make_input(nav_reconciled=False)
        result = evaluate_portfolio(item, RankingPolicy())
        assert result.eligible is False
        assert "nav_not_reconciled" in result.reasons

    def test_hard_breach(self):
        item = _make_input(open_hard_breaches=1)
        result = evaluate_portfolio(item, RankingPolicy())
        assert result.eligible is False
        assert "open_hard_risk_breach" in result.reasons

    def test_insufficient_history(self):
        item = _make_input(inception_at=datetime.now(UTC) - timedelta(days=30))
        result = evaluate_portfolio(item, RankingPolicy(minimum_history_days=90))
        assert result.eligible is False
        assert "insufficient_track_record" in result.reasons

    def test_missing_components(self):
        item = _make_input(components={})
        result = evaluate_portfolio(item, RankingPolicy())
        assert result.eligible is False
        assert any("missing_components" in r for r in result.reasons)

    def test_penalties_reduce_score(self):
        item = _make_input(
            open_soft_breaches=2,
            expired_theses=1,
            low_liquidity=True,
            high_turnover=True,
        )
        result_clean = evaluate_portfolio(_make_input(), RankingPolicy())
        result_penalized = evaluate_portfolio(item, RankingPolicy())
        assert result_clean.score is not None
        assert result_penalized.score is not None
        assert result_penalized.score < result_clean.score

    def test_stale_data_penalty(self):
        item = _make_input(data_as_of=datetime.now(UTC) - timedelta(hours=48))
        result = evaluate_portfolio(item, RankingPolicy(maximum_data_age_hours=36))
        assert result.penalty > 0


@pytest.mark.unit
class TestRankPortfolios:
    def test_ranking_order(self):
        items = [_make_input(portfolio_id=f"p{i}") for i in range(3)]
        results = rank_portfolios(items)
        assert len(results) == 3
        for r in results:
            assert r.rank is not None

    def test_top_x(self):
        items = [_make_input(portfolio_id=f"p{i}") for i in range(5)]
        results = rank_portfolios(items)
        top = top_x(results, cohort=cohort_key(_make_input()), limit=2)
        assert len(top) == 2
        assert all(r.eligible for r in top)

    def test_top_x_invalid_limit(self):
        with pytest.raises(ValueError, match="positive"):
            top_x([], cohort="x", limit=0)

    def test_ineligible_not_ranked(self):
        items = [_make_input(portfolio_id="p1", stage=PortfolioStage.DRAFT)]
        results = rank_portfolios(items)
        assert results[0].rank is None


@pytest.mark.unit
class TestRecordRankingCalibration:
    def test_none_engine(self):
        from ia_investing.domain.portfolio_ranking import record_ranking_calibration
        record_ranking_calibration([])  # should not raise
