"""Unit tests for connectors.macro._sidra — IBGE SIDRA macro data."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from connectors.macro._sidra import (
    _parse_month_period,
    _parse_quarter_period,
    get_gdp,
    get_industrial_production,
)


@pytest.mark.unit
class TestParseQuarterPeriod:
    def test_valid(self):
        result = _parse_quarter_period("1 Trimestre 2026")
        assert result == date(2026, 3, 1)

    def test_q4(self):
        result = _parse_quarter_period("4 Trimestre 2025")
        assert result == date(2025, 12, 1)

    def test_invalid_returns_none(self):
        assert _parse_quarter_period("bad") is None

    def test_empty_returns_none(self):
        assert _parse_quarter_period("") is None


@pytest.mark.unit
class TestParseMonthPeriod:
    def test_janeiro(self):
        result = _parse_month_period("janeiro de 2026")
        assert result == date(2026, 1, 1)

    def test_dezembro(self):
        result = _parse_month_period("dezembro de 2025")
        assert result == date(2025, 12, 1)

    def test_case_insensitive(self):
        result = _parse_month_period("JULHO de 2026")
        assert result == date(2026, 7, 1)

    def test_invalid_returns_none(self):
        assert _parse_month_period("bad") is None

    def test_unknown_month_defaults_to_1(self):
        result = _parse_month_period("xyz de 2026")
        assert result == date(2026, 1, 1)


@pytest.mark.unit
class TestGetGdp:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        mock_client = AsyncMock()
        raw = '[{"id":1,"variable":"PIB"},{"D3N":"1 Trimestre 2026","V":"2345678"}]'
        mock_client.get_text = AsyncMock(return_value=raw)
        results = await get_gdp(quarter_count=1, client=mock_client)
        assert len(results) == 1
        assert results[0].indicator_name == "PIB"
        assert results[0].period_date == date(2026, 3, 1)

    @pytest.mark.asyncio
    async def test_invalid_json_returns_empty(self):
        mock_client = AsyncMock()
        mock_client.get_text = AsyncMock(return_value="not json")
        results = await get_gdp(client=mock_client)
        assert results == []

    @pytest.mark.asyncio
    async def test_skips_invalid_rows(self):
        mock_client = AsyncMock()
        raw = '[{"id":1},{"D3N":"1 Trimestre 2026","V":"1000"},{"D3N":"bad","V":"bad"}]'
        mock_client.get_text = AsyncMock(return_value=raw)
        results = await get_gdp(quarter_count=1, client=mock_client)
        assert len(results) == 1


@pytest.mark.unit
class TestGetIndustrialProduction:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        mock_client = AsyncMock()
        raw = '[{"id":1},{"D3N":"janeiro de 2026","V":"102.5"}]'
        mock_client.get_text = AsyncMock(return_value=raw)
        results = await get_industrial_production(month_count=1, client=mock_client)
        assert len(results) == 1
        assert results[0].indicator_name == "Produção Industrial"
        assert results[0].period_date == date(2026, 1, 1)
