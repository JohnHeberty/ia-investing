"""Unit tests for PaperPortfolioService — CRUD, weight calculations, NAV."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ia_investing.application.paper_portfolio import PaperPortfolioService


@pytest.fixture()
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture()
def service(mock_session: AsyncMock) -> PaperPortfolioService:
    return PaperPortfolioService(mock_session)


def _make_portfolio(**overrides: object) -> MagicMock:
    p = MagicMock()
    p.id = overrides.get("id", uuid.uuid4())
    p.name = overrides.get("name", "Test Portfolio")
    p.description = overrides.get("description", None)
    p.is_paper_trading = overrides.get("is_paper_trading", True)
    p.base_currency = overrides.get("base_currency", "BRL")
    p.organization_id = overrides.get("organization_id", uuid.uuid4())
    p.created_at = overrides.get("created_at", None)
    return p


def _make_position(**overrides: object) -> MagicMock:
    p = MagicMock()
    p.id = overrides.get("id", uuid.uuid4())
    p.portfolio_id = overrides.get("portfolio_id", uuid.uuid4())
    p.ticker_symbol = overrides.get("ticker_symbol", "PETR4")
    p.quantity = Decimal(str(overrides.get("quantity", 100)))
    p.avg_cost_per_share = Decimal(str(overrides.get("avg_cost_per_share", 25.0)))
    cp = overrides.get("current_price", 28.0)
    p.current_price = Decimal(str(cp)) if cp is not None else None
    p.weight_pct = overrides.get("weight_pct", None)
    p.issuer_id = overrides.get("issuer_id", None)
    return p


@pytest.mark.asyncio
@pytest.mark.unit
class TestCreatePortfolio:
    async def test_create_returns_dict(self, service: PaperPortfolioService, mock_session: AsyncMock) -> None:
        result = await service.create(name="My Portfolio", description="desc", base_currency="BRL")
        assert result["name"] == "My Portfolio"
        assert result["description"] == "desc"
        assert result["is_paper_trading"] is True
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()

    async def test_create_with_initial_capital(
        self, service: PaperPortfolioService, mock_session: AsyncMock
    ) -> None:
        result = await service.create(name="Cap", initial_capital=100000.0)
        assert result["name"] == "Cap"
        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.initial_capital == 100000.0

    async def test_create_with_organization(
        self, service: PaperPortfolioService, mock_session: AsyncMock
    ) -> None:
        org_id = uuid.uuid4()
        result = await service.create(name="Org", organization_id=org_id)
        assert result["organization_id"] == str(org_id)


@pytest.mark.asyncio
@pytest.mark.unit
class TestListAll:
    async def test_list_all_empty(self, service: PaperPortfolioService, mock_session: AsyncMock) -> None:
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await service.list_all(uuid.uuid4())
        assert result == []

    async def test_list_all_with_positions(self, service: PaperPortfolioService, mock_session: AsyncMock) -> None:
        portfolio = _make_portfolio()
        position = _make_position(portfolio_id=portfolio.id)

        portfolio_result = MagicMock()
        portfolio_result.scalars.return_value.all.return_value = [portfolio]
        position_result = MagicMock()
        position_result.scalars.return_value.all.return_value = [position]
        mock_session.execute.side_effect = [portfolio_result, position_result]

        result = await service.list_all(portfolio.organization_id)
        assert len(result) == 1
        assert len(result[0]["positions"]) == 1
        assert result[0]["positions"][0]["ticker_symbol"] == "PETR4"


@pytest.mark.asyncio
@pytest.mark.unit
class TestGetWithPositions:
    async def test_get_returns_none_when_missing(self, service: PaperPortfolioService, mock_session: AsyncMock) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await service.get_with_positions(uuid.uuid4())
        assert result is None

    async def test_get_returns_portfolio_with_positions(
        self, service: PaperPortfolioService, mock_session: AsyncMock
    ) -> None:
        portfolio = _make_portfolio()
        position = _make_position(portfolio_id=portfolio.id)

        portfolio_result = MagicMock()
        portfolio_result.scalar_one_or_none.return_value = portfolio
        position_result = MagicMock()
        position_result.scalars.return_value.all.return_value = [position]
        mock_session.execute.side_effect = [portfolio_result, position_result]

        result = await service.get_with_positions(portfolio.id)
        assert result is not None
        assert result["name"] == portfolio.name
        assert len(result["positions"]) == 1


@pytest.mark.asyncio
@pytest.mark.unit
class TestAddPosition:
    async def test_add_position_portfolio_not_found(
        self, service: PaperPortfolioService, mock_session: AsyncMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(LookupError, match="Portfolio not found"):
            await service.add_position(uuid.uuid4(), "PETR4", 100, 25.0)

    @patch("ia_investing.application.paper_portfolio.get_current_price")
    async def test_add_position_success(
        self, mock_price: MagicMock, service: PaperPortfolioService, mock_session: AsyncMock
    ) -> None:
        portfolio = _make_portfolio()
        portfolio_result = MagicMock()
        portfolio_result.scalar_one_or_none.return_value = portfolio
        mock_session.execute.return_value = portfolio_result

        result = await service.add_position(
            portfolio.id, "PETR4", quantity=100, avg_cost_per_share=25.0, current_price=28.0
        )
        assert result["ticker_symbol"] == "PETR4"
        assert result["quantity"] == 100.0
        assert mock_session.add.call_count >= 1

    @patch("ia_investing.application.paper_portfolio.get_current_price")
    async def test_add_position_fetches_price_when_none(
        self, mock_price: MagicMock, service: PaperPortfolioService, mock_session: AsyncMock
    ) -> None:
        portfolio = _make_portfolio()
        portfolio_result = MagicMock()
        portfolio_result.scalar_one_or_none.return_value = portfolio
        mock_session.execute.return_value = portfolio_result
        mock_price.return_value = {"price": 30.0}

        result = await service.add_position(
            portfolio.id, "VALE3", quantity=50, avg_cost_per_share=10.0, current_price=None
        )
        assert result["current_price"] == 30.0

    @patch("ia_investing.application.paper_portfolio.get_current_price")
    async def test_add_position_handles_price_fetch_failure(
        self, mock_price: MagicMock, service: PaperPortfolioService, mock_session: AsyncMock
    ) -> None:
        portfolio = _make_portfolio()
        portfolio_result = MagicMock()
        portfolio_result.scalar_one_or_none.return_value = portfolio
        mock_session.execute.return_value = portfolio_result
        mock_price.side_effect = RuntimeError("network error")

        result = await service.add_position(
            portfolio.id, "ITUB4", quantity=100, avg_cost_per_share=20.0, current_price=None
        )
        assert result["current_price"] is None


@pytest.mark.asyncio
@pytest.mark.unit
class TestUpdatePosition:
    async def test_update_position_not_found(
        self, service: PaperPortfolioService, mock_session: AsyncMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await service.update_position(uuid.uuid4(), uuid.uuid4(), quantity=50)
        assert result is None

    async def test_update_position_success(
        self, service: PaperPortfolioService, mock_session: AsyncMock
    ) -> None:
        portfolio = _make_portfolio()
        position = _make_position(portfolio_id=portfolio.id)

        portfolio_result = MagicMock()
        portfolio_result.scalar_one_or_none.return_value = portfolio

        position_result = MagicMock()
        position_result.scalar_one_or_none.return_value = position

        positions_result = MagicMock()
        positions_result.scalars.return_value.all.return_value = [position]

        mock_session.execute.side_effect = [position_result, positions_result]

        result = await service.update_position(
            portfolio.id, position.id, quantity=200, current_price=30.0
        )
        assert result is not None
        assert result["quantity"] == 200.0
        assert result["current_price"] == 30.0

    @patch("ia_investing.application.paper_portfolio.get_current_price")
    async def test_update_ticker_fetches_new_price(
        self, mock_price: MagicMock, service: PaperPortfolioService, mock_session: AsyncMock
    ) -> None:
        position = _make_position()

        position_result = MagicMock()
        position_result.scalar_one_or_none.return_value = position

        positions_result = MagicMock()
        positions_result.scalars.return_value.all.return_value = [position]

        mock_session.execute.side_effect = [position_result, positions_result]
        mock_price.return_value = {"price": 42.0}

        result = await service.update_position(
            uuid.uuid4(), position.id, ticker_symbol="MGLU3"
        )
        assert result is not None
        assert result["current_price"] == 42.0


@pytest.mark.asyncio
@pytest.mark.unit
class TestDeletePosition:
    async def test_delete_position_not_found(
        self, service: PaperPortfolioService, mock_session: AsyncMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await service.delete_position(uuid.uuid4(), uuid.uuid4())
        assert result is False

    async def test_delete_position_success(
        self, service: PaperPortfolioService, mock_session: AsyncMock
    ) -> None:
        portfolio = _make_portfolio()
        position = _make_position(portfolio_id=portfolio.id)

        position_result = MagicMock()
        position_result.scalar_one_or_none.return_value = position
        positions_result = MagicMock()
        positions_result.scalars.return_value.all.return_value = []
        mock_session.execute.side_effect = [position_result, positions_result]

        result = await service.delete_position(portfolio.id, position.id)
        assert result is True
        mock_session.delete.assert_awaited_once_with(position)


@pytest.mark.asyncio
@pytest.mark.unit
class TestDeletePortfolio:
    async def test_delete_portfolio_not_found(
        self, service: PaperPortfolioService, mock_session: AsyncMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await service.delete_portfolio(uuid.uuid4())
        assert result is False

    async def test_delete_portfolio_with_executions_raises(
        self, service: PaperPortfolioService, mock_session: AsyncMock
    ) -> None:
        portfolio = _make_portfolio()
        portfolio_result = MagicMock()
        portfolio_result.scalar_one_or_none.return_value = portfolio

        count_result = MagicMock()
        count_result.scalar_one.return_value = 5
        mock_session.execute.side_effect = [portfolio_result, count_result]

        with pytest.raises(RuntimeError, match="active executions"):
            await service.delete_portfolio(portfolio.id)

    async def test_delete_portfolio_success(
        self, service: PaperPortfolioService, mock_session: AsyncMock
    ) -> None:
        portfolio = _make_portfolio()
        portfolio_result = MagicMock()
        portfolio_result.scalar_one_or_none.return_value = portfolio

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        mock_session.execute.side_effect = [portfolio_result, count_result]

        result = await service.delete_portfolio(portfolio.id)
        assert result is True
        mock_session.delete.assert_awaited_once_with(portfolio)


@pytest.mark.asyncio
@pytest.mark.unit
class TestRecalculateWeights:
    async def test_recalculate_weights_empty_positions(
        self, service: PaperPortfolioService, mock_session: AsyncMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await service._recalculate_weights(uuid.uuid4())
        mock_session.flush.assert_awaited()

    async def test_recalculate_weights_proportional(
        self, service: PaperPortfolioService, mock_session: AsyncMock
    ) -> None:
        pos_a = _make_position(ticker_symbol="PETR4", quantity=100, current_price=20.0)
        pos_b = _make_position(ticker_symbol="VALE3", quantity=50, current_price=20.0)
        # total = 100*20 + 50*20 = 3000; PETR4=2000/3000=0.667, VALE3=1000/3000=0.333

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [pos_a, pos_b]
        mock_session.execute.return_value = mock_result

        await service._recalculate_weights(uuid.uuid4())

        assert float(pos_a.weight_pct) == pytest.approx(2000 / 3000, rel=1e-3)
        assert float(pos_b.weight_pct) == pytest.approx(1000 / 3000, rel=1e-3)

    async def test_recalculate_weights_falls_back_to_avg_cost(
        self, service: PaperPortfolioService, mock_session: AsyncMock
    ) -> None:
        pos = _make_position(ticker_symbol="PETR4", quantity=100, current_price=None, avg_cost_per_share=15.0)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [pos]
        mock_session.execute.return_value = mock_result

        await service._recalculate_weights(uuid.uuid4())
        # Single position with total > 0 → weight should be 1.0
        assert float(pos.weight_pct) == pytest.approx(1.0, rel=1e-3)

    async def test_recalculate_weights_zero_total(
        self, service: PaperPortfolioService, mock_session: AsyncMock
    ) -> None:
        pos = _make_position(quantity=0, current_price=Decimal("0"))

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [pos]
        mock_session.execute.return_value = mock_result

        await service._recalculate_weights(uuid.uuid4())
        assert float(pos.weight_pct) == 0.0


@pytest.mark.unit
class TestDictConversion:
    def test_to_dict(self) -> None:
        portfolio = _make_portfolio(name="Test")
        result = PaperPortfolioService._to_dict(portfolio)
        assert result["name"] == "Test"
        assert "id" in result
        assert "is_paper_trading" in result

    def test_position_to_dict(self) -> None:
        pos = _make_position(ticker_symbol="ITUB4", quantity=100)
        result = PaperPortfolioService._position_to_dict(pos)
        assert result["ticker_symbol"] == "ITUB4"
        assert result["quantity"] == 100.0

    def test_position_to_dict_with_none_weight(self) -> None:
        pos = _make_position(weight_pct=None)
        result = PaperPortfolioService._position_to_dict(pos)
        assert result["weight_pct"] is None
