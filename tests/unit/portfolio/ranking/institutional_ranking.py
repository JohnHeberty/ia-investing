"""Tests for portfolio ranking by comparable category with penalty scoring."""

from __future__ import annotations

from decimal import Decimal

from ia_investing.domain.institutional_portfolio import (
    ComparableCategory,
    PortfolioRankingEntry,
    calculate_penalty_score,
    rank_portfolios_by_category,
)


def _entry(
    portfolio_id: str = "p1",
    strategy_type: str = "momentum",
    risk_level: str = "moderate",
    horizon: str = "medium",
    currency: str = "BRL",
    stage: str = "paper_live",
    score: Decimal = Decimal("0.80"),
) -> PortfolioRankingEntry:
    return PortfolioRankingEntry(
        portfolio_id=portfolio_id,
        strategy_type=strategy_type,
        risk_level=risk_level,
        horizon=horizon,
        currency=currency,
        stage=stage,
        score=score,
        penalties=(),
        final_score=score,
    )


class TestCalculatePenaltyScore:
    def test_no_penalties(self) -> None:
        final, penalties = calculate_penalty_score(
            base_score=Decimal("0.90"),
            thesis_freshness=Decimal("1.0"),
            has_critical_breach=False,
            data_staleness_days=0,
            version_age_days=0,
        )
        assert final == Decimal("0.90")
        assert penalties == ()

    def test_thesis_expired(self) -> None:
        final, penalties = calculate_penalty_score(
            base_score=Decimal("0.80"),
            thesis_freshness=Decimal("0.3"),
            has_critical_breach=False,
            data_staleness_days=0,
            version_age_days=0,
        )
        assert "thesis_expired" in penalties
        assert final == Decimal("0.50")

    def test_thesis_freshness_low(self) -> None:
        final, penalties = calculate_penalty_score(
            base_score=Decimal("0.80"),
            thesis_freshness=Decimal("0.6"),
            has_critical_breach=False,
            data_staleness_days=0,
            version_age_days=0,
        )
        assert "thesis_freshness_low" in penalties
        assert final == Decimal("0.70")

    def test_critical_breach(self) -> None:
        final, penalties = calculate_penalty_score(
            base_score=Decimal("0.80"),
            thesis_freshness=Decimal("1.0"),
            has_critical_breach=True,
            data_staleness_days=0,
            version_age_days=0,
        )
        assert "critical_breach" in penalties
        assert final == Decimal("0.30")

    def test_data_stale(self) -> None:
        final, penalties = calculate_penalty_score(
            base_score=Decimal("0.80"),
            thesis_freshness=Decimal("1.0"),
            has_critical_breach=False,
            data_staleness_days=45,
            version_age_days=0,
        )
        assert "data_stale" in penalties
        assert final == Decimal("0.60")

    def test_version_stale(self) -> None:
        final, penalties = calculate_penalty_score(
            base_score=Decimal("0.80"),
            thesis_freshness=Decimal("1.0"),
            has_critical_breach=False,
            data_staleness_days=0,
            version_age_days=120,
        )
        assert "version_stale" in penalties
        assert final == Decimal("0.70")

    def test_multiple_penalties_cumulative(self) -> None:
        final, penalties = calculate_penalty_score(
            base_score=Decimal("0.90"),
            thesis_freshness=Decimal("0.3"),
            has_critical_breach=False,
            data_staleness_days=45,
            version_age_days=120,
        )
        assert len(penalties) == 3
        assert final >= Decimal(0)

    def test_score_clamped_at_zero(self) -> None:
        final, _ = calculate_penalty_score(
            base_score=Decimal("0.10"),
            thesis_freshness=Decimal("0.3"),
            has_critical_breach=True,
            data_staleness_days=45,
            version_age_days=120,
        )
        assert final == Decimal(0)

    def test_score_clamped_at_one(self) -> None:
        final, _ = calculate_penalty_score(
            base_score=Decimal("1.0"),
            thesis_freshness=Decimal("1.0"),
            has_critical_breach=False,
            data_staleness_days=0,
            version_age_days=0,
        )
        assert final == Decimal("1")


class TestComparableCategoryKey:
    def test_creates_category_from_entry(self) -> None:
        entry = _entry()
        cat = ComparableCategory(
            strategy_type="momentum",
            risk_level="moderate",
            horizon="medium",
            currency="BRL",
            stage="paper_live",
        )
        assert (
            ComparableCategory(
                strategy_type=entry.strategy_type,
                risk_level=entry.risk_level,
                horizon=entry.horizon,
                currency=entry.currency,
                stage=entry.stage,
            )
            == cat
        )


class TestRankPortfoliosByCategory:
    def test_same_category_sorted_by_final_score(self) -> None:
        e1 = _entry(portfolio_id="p1", score=Decimal("0.60"))
        e1 = PortfolioRankingEntry(
            e1.portfolio_id,
            e1.strategy_type,
            e1.risk_level,
            e1.horizon,
            e1.currency,
            e1.stage,
            e1.score,
            e1.penalties,
            Decimal("0.60"),
        )
        e2 = _entry(portfolio_id="p2", score=Decimal("0.90"))
        e2 = PortfolioRankingEntry(
            e2.portfolio_id,
            e2.strategy_type,
            e2.risk_level,
            e2.horizon,
            e2.currency,
            e2.stage,
            e2.score,
            e2.penalties,
            Decimal("0.90"),
        )
        e3 = _entry(portfolio_id="p3", score=Decimal("0.75"))
        e3 = PortfolioRankingEntry(
            e3.portfolio_id,
            e3.strategy_type,
            e3.risk_level,
            e3.horizon,
            e3.currency,
            e3.stage,
            e3.score,
            e3.penalties,
            Decimal("0.75"),
        )
        result = rank_portfolios_by_category((e1, e2, e3))
        assert len(result) == 1
        group = next(iter(result.values()))
        assert [e.portfolio_id for e in group] == ["p2", "p3", "p1"]

    def test_different_categories_separated(self) -> None:
        e1 = _entry(portfolio_id="p1", strategy_type="momentum")
        e2 = _entry(portfolio_id="p2", strategy_type="value")
        result = rank_portfolios_by_category((e1, e2))
        assert len(result) == 2

    def test_empty_input(self) -> None:
        result = rank_portfolios_by_category(())
        assert result == {}
