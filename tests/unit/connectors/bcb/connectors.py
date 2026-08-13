"""Unit tests for connectors.macro._bcb — BCB time-series fetching."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from connectors.macro._bcb import (
    MacroObservation,
    _parse_bcb_date,
    _parse_value,
    get_bcb_series,
    get_ipca,
    get_selic,
    get_usd_brl,
)


@pytest.mark.unit
class TestParseBcbDate:
    def test_valid(self):
        assert _parse_bcb_date("01/01/2026") == date(2026, 1, 1)

    def test_strips_whitespace(self):
        assert _parse_bcb_date("  15/06/2026  ") == date(2026, 6, 15)

    def test_invalid_returns_none(self):
        assert _parse_bcb_date("not-a-date") is None

    def test_none_returns_none(self):
        assert _parse_bcb_date(None) is None  # type: ignore[arg-type]


@pytest.mark.unit
class TestParseValue:
    def test_simple(self):
        assert _parse_value("12.5") == 12.5

    def test_comma_decimal(self):
        assert _parse_value("12,5") == 12.5

    def test_strips_whitespace(self):
        assert _parse_value("  10.0  ") == 10.0

    def test_invalid_returns_none(self):
        assert _parse_value("abc") is None

    def test_none_returns_none(self):
        assert _parse_value(None) is None  # type: ignore[arg-type]


@pytest.mark.unit
class TestGetBcbSeries:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        mock_client = AsyncMock()
        mock_client.get_text = AsyncMock(return_value='[{"data":"01/01/2026","valor":"13.75"},{"data":"02/01/2026","valor":"13.80"}]')
        results = await get_bcb_series(432, date(2026, 1, 1), date(2026, 1, 31), client=mock_client, indicator_name="SELIC", unit="% a.a.")
        assert len(results) == 2
        assert results[0].value == 13.75
        assert results[0].indicator_name == "SELIC"
        assert results[0].series_code == 432

    @pytest.mark.asyncio
    async def test_invalid_json_returns_empty(self):
        mock_client = AsyncMock()
        mock_client.get_text = AsyncMock(return_value="not json")
        results = await get_bcb_series(432, date(2026, 1, 1), date(2026, 1, 31), client=mock_client)
        assert results == []

    @pytest.mark.asyncio
    async def test_skips_invalid_rows(self):
        mock_client = AsyncMock()
        mock_client.get_text = AsyncMock(return_value='[{"data":"01/01/2026","valor":"13.75"},{"data":"bad","valor":"bad"},{"data":"02/01/2026","valor":"N/A"}]')
        results = await get_bcb_series(432, date(2026, 1, 1), date(2026, 1, 31), client=mock_client)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_empty_indicator_name_defaults(self):
        mock_client = AsyncMock()
        mock_client.get_text = AsyncMock(return_value='[{"data":"01/01/2026","valor":"100"}]')
        results = await get_bcb_series(999, date(2026, 1, 1), date(2026, 1, 31), client=mock_client)
        assert results[0].indicator_name == "BCB_999"


@pytest.mark.unit
class TestConvenienceFunctions:
    @pytest.mark.asyncio
    async def test_get_selic(self):
        mock_client = AsyncMock()
        mock_client.get_text = AsyncMock(return_value='[{"data":"01/01/2026","valor":"13.75"}]')
        results = await get_selic(date(2026, 1, 1), date(2026, 1, 31), client=mock_client)
        assert results[0].indicator_name == "SELIC"
        assert results[0].unit == "% a.a."

    @pytest.mark.asyncio
    async def test_get_ipca(self):
        mock_client = AsyncMock()
        mock_client.get_text = AsyncMock(return_value='[{"data":"01/01/2026","valor":"0.52"}]')
        results = await get_ipca(date(2026, 1, 1), date(2026, 1, 31), client=mock_client)
        assert results[0].indicator_name == "IPCA"
        assert results[0].unit == "% a.m."

    @pytest.mark.asyncio
    async def test_get_usd_brl(self):
        mock_client = AsyncMock()
        mock_client.get_text = AsyncMock(return_value='[{"data":"01/01/2026","valor":"5.85"}]')
        results = await get_usd_brl(date(2026, 1, 1), date(2026, 1, 31), client=mock_client)
        assert results[0].indicator_name == "USD/BRL"
        assert results[0].unit == "BRL"
