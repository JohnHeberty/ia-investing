"""Unit tests for connectors.policy._bcb_sgs — BCB SGS time series."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import AsyncMock

import pytest

from connectors.policy._bcb_sgs import (
    BCBSGSClient,
    SGSObservation,
    _parse_sgs_date,
    _parse_sgs_response,
    _parse_value,
)


@pytest.mark.unit
class TestParseSGSDate:
    def test_valid(self) -> None:
        assert _parse_sgs_date("01/01/2026") == date(2026, 1, 1)

    def test_strips_whitespace(self) -> None:
        assert _parse_sgs_date("  15/06/2026  ") == date(2026, 6, 15)

    def test_invalid_returns_none(self) -> None:
        assert _parse_sgs_date("not-a-date") is None

    def test_none_returns_none(self) -> None:
        assert _parse_sgs_date(None) is None  # type: ignore[arg-type]


@pytest.mark.unit
class TestParseValue:
    def test_simple(self) -> None:
        assert _parse_value("12.5") == 12.5

    def test_comma_decimal(self) -> None:
        assert _parse_value("12,5") == 12.5

    def test_strips_whitespace(self) -> None:
        assert _parse_value("  10.0  ") == 10.0

    def test_invalid_returns_none(self) -> None:
        assert _parse_value("abc") is None

    def test_none_returns_none(self) -> None:
        assert _parse_value(None) is None  # type: ignore[arg-type]


@pytest.mark.unit
class TestParseSGSResponse:
    def test_happy_path(self) -> None:
        data = [
            {"data": "01/01/2026", "valor": "13.75"},
            {"data": "02/01/2026", "valor": "13.80"},
        ]
        result = _parse_sgs_response(json.dumps(data))
        assert len(result) == 2
        assert result[0].date == date(2026, 1, 1)
        assert result[0].value == 13.75
        assert result[1].date == date(2026, 1, 2)
        assert result[1].value == 13.80

    def test_invalid_json_returns_empty(self) -> None:
        assert _parse_sgs_response("not json") == []

    def test_non_list_returns_empty(self) -> None:
        assert _parse_sgs_response('{"key": "value"}') == []

    def test_skips_invalid_rows(self) -> None:
        data = [
            {"data": "01/01/2026", "valor": "13.75"},
            {"data": "bad", "valor": "bad"},
            {"data": "02/01/2026", "valor": "N/A"},
        ]
        result = _parse_sgs_response(json.dumps(data))
        assert len(result) == 1

    def test_skips_non_dict_items(self) -> None:
        assert _parse_sgs_response(json.dumps([1, "text", True])) == []

    def test_empty_list(self) -> None:
        assert _parse_sgs_response("[]") == []

    def test_comma_decimal_in_response(self) -> None:
        data = [{"data": "01/01/2026", "valor": "12,5"}]
        result = _parse_sgs_response(json.dumps(data))
        assert len(result) == 1
        assert result[0].value == 12.5


@pytest.mark.unit
class TestBCBSGSClient:
    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        mock_http = AsyncMock()
        data = [
            {"data": "01/01/2026", "valor": "13.75"},
            {"data": "02/01/2026", "valor": "13.80"},
        ]
        mock_http.get_text = AsyncMock(return_value=json.dumps(data))
        client = BCBSGSClient(http=mock_http)

        result = await client.fetch_series(
            series_code=432,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        assert len(result) == 2
        assert result[0].date == date(2026, 1, 1)
        assert result[0].value == 13.75
        mock_http.get_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_json_returns_empty(self) -> None:
        mock_http = AsyncMock()
        mock_http.get_text = AsyncMock(return_value="not json")
        client = BCBSGSClient(http=mock_http)

        result = await client.fetch_series(
            series_code=432,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_skips_invalid_rows(self) -> None:
        mock_http = AsyncMock()
        data = [
            {"data": "01/01/2026", "valor": "13.75"},
            {"data": "bad", "valor": "bad"},
            {"data": "02/01/2026", "valor": "N/A"},
        ]
        mock_http.get_text = AsyncMock(return_value=json.dumps(data))
        client = BCBSGSClient(http=mock_http)

        result = await client.fetch_series(
            series_code=432,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_network_error_propagates(self) -> None:
        mock_http = AsyncMock()
        mock_http.get_text = AsyncMock(side_effect=ConnectionError("timeout"))
        client = BCBSGSClient(http=mock_http)

        with pytest.raises(ConnectionError, match="timeout"):
            await client.fetch_series(
                series_code=432,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 31),
            )

    @pytest.mark.asyncio
    async def test_empty_response(self) -> None:
        mock_http = AsyncMock()
        mock_http.get_text = AsyncMock(return_value="[]")
        client = BCBSGSClient(http=mock_http)

        result = await client.fetch_series(
            series_code=432,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        assert result == []

    def test_default_http_client(self) -> None:
        client = BCBSGSClient()
        assert client._http is not None

    def test_frozen_dataclass(self) -> None:
        obs = SGSObservation(date=date(2026, 1, 1), value=1.0)
        assert obs.date == date(2026, 1, 1)
        assert obs.value == 1.0
