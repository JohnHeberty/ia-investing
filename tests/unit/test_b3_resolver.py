from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ia_investing.integrations.connectors.b3_resolver import B3Resolver


@pytest.fixture()
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def resolver(mock_db: MagicMock) -> B3Resolver:
    return B3Resolver(db=mock_db)


class TestLookupByTicker:
    async def test_returns_profile_with_market_data(self, resolver: B3Resolver) -> None:
        mock_row = MagicMock()
        mock_row.ticker = "PETR4"
        mock_row.exchange_code = "BOVESPA"
        mock_row.market_segment = "Novo Mercado"

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(one_or_none=MagicMock(return_value=mock_row)))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        resolver._db.session = MagicMock(return_value=mock_session)

        mock_trades = [
            MagicMock(
                trade_date=date(2025, 7, 20),
                ticker="PETR4",
                preco_ultimo=28.50,
                qtd_titulos_negociados=5000000,
            ),
            MagicMock(
                trade_date=date(2025, 7, 21),
                ticker="PETR4",
                preco_ultimo=29.10,
                qtd_titulos_negociados=6000000,
            ),
        ]

        with patch(
            "ia_investing.integrations.connectors.b3_resolver.get_cotahist_year",
            new_callable=AsyncMock,
            return_value=mock_trades,
        ):
            result = await resolver.lookup_by_ticker("PETR4")

        assert result is not None
        assert result.ticker == "PETR4"
        assert result.exchange == "BOVESPA"
        assert result.market_segment == "Novo Mercado"
        assert result.closing_price == Decimal("29.10")
        assert result.last_trade_date == date(2025, 7, 21)
        assert result.average_volume_30d == Decimal("5500000")

    async def test_returns_none_when_ticker_not_in_db(self, resolver: B3Resolver) -> None:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(one_or_none=MagicMock(return_value=None)))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        resolver._db.session = MagicMock(return_value=mock_session)

        result = await resolver.lookup_by_ticker("XXXX")
        assert result is None

    async def test_returns_profile_without_market_data_on_cotahist_error(self, resolver: B3Resolver) -> None:
        mock_row = MagicMock()
        mock_row.ticker = "PETR4"
        mock_row.exchange_code = "BOVESPA"
        mock_row.market_segment = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(one_or_none=MagicMock(return_value=mock_row)))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        resolver._db.session = MagicMock(return_value=mock_session)

        with patch(
            "ia_investing.integrations.connectors.b3_resolver.get_cotahist_year",
            new_callable=AsyncMock,
            side_effect=Exception("network error"),
        ):
            result = await resolver.lookup_by_ticker("PETR4")

        assert result is not None
        assert result.ticker == "PETR4"
        assert result.closing_price is None
        assert result.average_volume_30d is None

    async def test_returns_profile_with_empty_trades(self, resolver: B3Resolver) -> None:
        mock_row = MagicMock()
        mock_row.ticker = "PETR4"
        mock_row.exchange_code = "BOVESPA"
        mock_row.market_segment = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(one_or_none=MagicMock(return_value=mock_row)))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        resolver._db.session = MagicMock(return_value=mock_session)

        with patch(
            "ia_investing.integrations.connectors.b3_resolver.get_cotahist_year",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await resolver.lookup_by_ticker("PETR4")

        assert result is not None
        assert result.closing_price is None
