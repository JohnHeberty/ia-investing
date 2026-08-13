"""Unit tests for PortfolioOptimizationService and BackendPortfolioOptimizationService (portfolio.py)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database.models.instrument_master import Listing
from database.models.market_data import MarketBar
from database.models.portfolio_domain import ModelPortfolio, OptimizationRun, StrategyMandate
from ia_investing.application.portfolio import BackendPortfolioOptimizationService, PortfolioOptimizationService
from ia_investing.domain.identity import InstitutionalAccessContext


def _ctx(
    *,
    subject: str = "pm-1",
    org_id: UUID | None = None,
    team_ids: frozenset[UUID] | None = None,
    perms: frozenset[str] | None = None,
) -> InstitutionalAccessContext:
    org = org_id or uuid4()
    return InstitutionalAccessContext(
        subject=subject,
        organization_id=org,
        team_ids=team_ids or frozenset({uuid4()}),
        permissions=perms or frozenset({"portfolio:optimize"}),
        environment="paper",
    )


@pytest.mark.unit
class TestPortfolioOptimizationService:
    @pytest.mark.asyncio
    async def test_optimize_delegates_to_optimizer(self) -> None:
        svc = PortfolioOptimizationService()
        mock_result = MagicMock()
        mock_result.status = "optimal"
        mock_result.weights = {"A": 0.5, "B": 0.5}
        mock_result.expected_return = 0.1
        mock_result.expected_risk = 0.15
        mock_result.sharpe_ratio = 0.67
        mock_result.turnover = 0.0
        mock_result.transactions = {}
        mock_result.diagnostics = {}
        mock_result.slacks = {}

        with patch("ia_investing.application.portfolio.PortfolioOptimizer") as MockOpt:
            mock_optimizer = AsyncMock()
            mock_optimizer.optimize.return_value = mock_result
            MockOpt.return_value = mock_optimizer
            result = await svc.optimize(
                returns_data=[{"A": 0.01, "B": 0.02}],
                current_weights=None,
                risk_aversion=1.0,
                max_weight=0.5,
                max_sector=0.3,
                max_turnover=0.5,
            )
            assert result["status"] == "optimal"
            assert result["weights"] == {"A": 0.5, "B": 0.5}


@pytest.mark.unit
class TestBackendPortfolioOptimizationService:
    def _setup_session(self, *, portfolio: ModelPortfolio | None = None, mandate: StrategyMandate | None = None):
        session = AsyncMock()
        if portfolio is not None and mandate is not None:
            session.get = AsyncMock(side_effect=[portfolio, mandate])
        elif portfolio is not None:
            session.get = AsyncMock(side_effect=[portfolio, mandate])
        return session

    @pytest.mark.asyncio
    async def test_optimize_portfolio_not_found(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        svc = BackendPortfolioOptimizationService(session)
        with pytest.raises(LookupError, match="portfolio not found"):
            await svc.optimize(uuid4(), datetime.now(UTC), _ctx())

    @pytest.mark.asyncio
    async def test_optimize_mandate_missing(self) -> None:
        session = AsyncMock()
        org = uuid4()
        team = uuid4()
        portfolio = MagicMock(spec=ModelPortfolio)
        portfolio.id = uuid4()
        portfolio.organization_id = org
        portfolio.owner_team_id = team
        portfolio.mandate_id = uuid4()
        session.get = AsyncMock(side_effect=[portfolio, None])
        svc = BackendPortfolioOptimizationService(session)
        with pytest.raises(RuntimeError, match="mandate is missing"):
            await svc.optimize(portfolio.id, datetime.now(UTC), _ctx(org_id=org, team_ids=frozenset({team})))

    @pytest.mark.asyncio
    async def test_optimize_invalid_instrument_ids(self) -> None:
        session = AsyncMock()
        org = uuid4()
        team = uuid4()
        portfolio = MagicMock(spec=ModelPortfolio)
        portfolio.id = uuid4()
        portfolio.organization_id = org
        portfolio.owner_team_id = team
        mandate = MagicMock(spec=StrategyMandate)
        mandate.config = {
            "universe_definition": {"instrument_ids": ["not-a-uuid"]},
            "exclusions": {},
            "concentration_limits": {},
            "max_turnover": 0.25,
            "min_cash_weight": 0.05,
            "max_cash_weight": 0.15,
        }
        session.get = AsyncMock(side_effect=[portfolio, mandate])
        svc = BackendPortfolioOptimizationService(session)
        with pytest.raises(ValueError, match="invalid instrument IDs"):
            await svc.optimize(portfolio.id, datetime.now(UTC), _ctx(org_id=org, team_ids=frozenset({team})))

    @pytest.mark.asyncio
    async def test_optimize_insufficient_price_history(self) -> None:
        session = AsyncMock()
        org = uuid4()
        team = uuid4()
        portfolio = MagicMock(spec=ModelPortfolio)
        portfolio.id = uuid4()
        portfolio.organization_id = org
        portfolio.owner_team_id = team
        mandate = MagicMock(spec=StrategyMandate)
        iid = uuid4()
        mandate.config = {
            "universe_definition": {"instrument_ids": [str(iid)]},
            "exclusions": {},
            "concentration_limits": {},
            "max_turnover": 0.25,
            "min_cash_weight": 0.05,
            "max_cash_weight": 0.15,
        }
        session.get = AsyncMock(side_effect=[portfolio, mandate])
        result_mock = MagicMock()
        result_mock.all.return_value = []
        session.execute = AsyncMock(return_value=result_mock)
        svc = BackendPortfolioOptimizationService(session)
        with pytest.raises(ValueError, match="insufficient"):
            await svc.optimize(portfolio.id, datetime.now(UTC), _ctx(org_id=org, team_ids=frozenset({team})))

    @pytest.mark.asyncio
    async def test_optimize_existing_run_returned(self) -> None:
        session = AsyncMock()
        org = uuid4()
        team = uuid4()
        portfolio = MagicMock(spec=ModelPortfolio)
        portfolio.id = uuid4()
        portfolio.organization_id = org
        portfolio.owner_team_id = team
        mandate = MagicMock(spec=StrategyMandate)
        iid = uuid4()
        mandate.config = {
            "universe_definition": {"instrument_ids": [str(iid)]},
            "exclusions": {},
            "concentration_limits": {},
            "max_turnover": 0.25,
            "min_cash_weight": 0.05,
            "max_cash_weight": 0.15,
        }
        session.get = AsyncMock(side_effect=[portfolio, mandate])

        base = datetime(2026, 1, 1, tzinfo=UTC)
        price_rows = [(iid, base, Decimal("100")), (iid, base.replace(day=2), Decimal("101")), (iid, base.replace(day=3), Decimal("102"))]
        price_result = MagicMock()
        price_result.all.return_value = price_rows

        existing_run = MagicMock(spec=OptimizationRun)
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = existing_run

        call_count = 0

        async def fake_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return price_result
            return existing_result

        session.execute = AsyncMock(side_effect=fake_execute)
        svc = BackendPortfolioOptimizationService(session)
        result = await svc.optimize(portfolio.id, base.replace(day=5), _ctx(org_id=org, team_ids=frozenset({team})))
        assert result is existing_run

    @pytest.mark.asyncio
    async def test_optimize_integrity_error_fallback(self) -> None:
        from sqlalchemy.exc import IntegrityError

        session = AsyncMock()
        org = uuid4()
        team = uuid4()
        portfolio = MagicMock(spec=ModelPortfolio)
        portfolio.id = uuid4()
        portfolio.organization_id = org
        portfolio.owner_team_id = team
        mandate = MagicMock(spec=StrategyMandate)
        iid = uuid4()
        mandate.config = {
            "universe_definition": {"instrument_ids": [str(iid)]},
            "exclusions": {},
            "concentration_limits": {},
            "max_turnover": 0.25,
            "min_cash_weight": 0.05,
            "max_cash_weight": 0.15,
        }
        session.get = AsyncMock(side_effect=[portfolio, mandate])

        base = datetime(2026, 1, 1, tzinfo=UTC)
        price_rows = [(iid, base, Decimal("100")), (iid, base.replace(day=2), Decimal("101")), (iid, base.replace(day=3), Decimal("102"))]
        price_result = MagicMock()
        price_result.all.return_value = price_rows

        fallback_run = MagicMock(spec=OptimizationRun)
        fallback_result = MagicMock()
        fallback_result.scalar_one_or_none.return_value = fallback_run

        call_count = 0

        async def fake_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return price_result
            if call_count == 2:
                return MagicMock(scalar_one_or_none=MagicMock(return_value=None))
            return fallback_result

        session.execute = AsyncMock(side_effect=fake_execute)
        session.flush = AsyncMock(side_effect=IntegrityError("test", {}, Exception()))
        session.rollback = AsyncMock()

        svc = BackendPortfolioOptimizationService(session)

        with patch("ia_investing.application.portfolio.PortfolioOptimizer") as MockOpt:
            mock_optimizer = AsyncMock()
            mock_result = MagicMock()
            mock_result.status = "optimal"
            mock_result.weights = {}
            mock_result.transactions = {}
            mock_result.slacks = {}
            mock_result.diagnostics = {}
            mock_optimizer.optimize.return_value = mock_result
            MockOpt.return_value = mock_optimizer

            result = await svc.optimize(portfolio.id, base.replace(day=5), _ctx(org_id=org, team_ids=frozenset({team})))
            assert result is fallback_run
