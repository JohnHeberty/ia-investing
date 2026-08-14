"""Unit tests for connectors.policy._ibge_sidra — IBGE SIDRA aggregated data."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from connectors.policy._ibge_sidra import (
    IBGESIDRAClient,
    SIDRATableMetadata,
    _parse_sidra_response,
)


@pytest.mark.unit
class TestParseSIDRAResponse:
    def test_happy_path(self) -> None:
        data = [
            {"D3N": "Brasil", "V": "1000"},
            {"D3N": "Região Sudeste", "V": "500"},
        ]
        result = _parse_sidra_response(json.dumps(data))
        assert len(result) == 2
        assert result[0]["D3N"] == "Brasil"
        assert result[1]["V"] == "500"

    def test_invalid_json_returns_empty(self) -> None:
        assert _parse_sidra_response("not json") == []

    def test_non_list_returns_empty(self) -> None:
        assert _parse_sidra_response('{"key": "value"}') == []

    def test_skips_non_dict_items(self) -> None:
        assert _parse_sidra_response(json.dumps([1, "text", True])) == []

    def test_empty_list(self) -> None:
        assert _parse_sidra_response("[]") == []

    def test_nested_dict_items(self) -> None:
        data = [{"a": 1}, {"b": {"c": 2}}]
        result = _parse_sidra_response(json.dumps(data))
        assert len(result) == 2


@pytest.mark.unit
class TestIBGESIDRAClient:
    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        mock_http = AsyncMock()
        data = [
            {"D3N": "Brasil", "V": "2345678"},
            {"D3N": "Região Norte", "V": "123456"},
        ]
        mock_http.get_text = AsyncMock(return_value=json.dumps(data))
        client = IBGESIDRAClient(http=mock_http)

        result = await client.fetch_table(
            table_id=5938,
            variables=[3700],
            territorial_level=1,
        )

        assert len(result) == 2
        assert result[0]["D3N"] == "Brasil"
        mock_http.get_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_with_period(self) -> None:
        mock_http = AsyncMock()
        data = [{"D3N": "Brasil", "V": "1000"}]
        mock_http.get_text = AsyncMock(return_value=json.dumps(data))
        client = IBGESIDRAClient(http=mock_http)

        result = await client.fetch_table(
            table_id=5938,
            variables=[3700],
            territorial_level=2,
            period="last 4 quarters",
        )

        assert len(result) == 1
        mock_http.get_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_variables_raises(self) -> None:
        client = IBGESIDRAClient(http=AsyncMock())
        with pytest.raises(ValueError, match="At least one variable"):
            await client.fetch_table(table_id=5938, variables=[])

    @pytest.mark.asyncio
    async def test_fetch_table_with_periods_happy_path(self) -> None:
        mock_http = AsyncMock()
        data = [{"D3N": "Brasil", "V": "5000"}]
        mock_http.get_text = AsyncMock(return_value=json.dumps(data))
        client = IBGESIDRAClient(http=mock_http)

        result = await client.fetch_table_with_periods(
            table_id=5938,
            variables=[3700],
            territorial_level=1,
            periods=["202601", "202602"],
        )

        assert len(result) == 1
        mock_http.get_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_table_with_periods_empty_variables_raises(self) -> None:
        client = IBGESIDRAClient(http=AsyncMock())
        with pytest.raises(ValueError, match="At least one variable"):
            await client.fetch_table_with_periods(table_id=5938, variables=[], periods=["202601"])

    @pytest.mark.asyncio
    async def test_fetch_table_with_periods_empty_periods_raises(self) -> None:
        client = IBGESIDRAClient(http=AsyncMock())
        with pytest.raises(ValueError, match="At least one period"):
            await client.fetch_table_with_periods(table_id=5938, variables=[3700], periods=[])

    @pytest.mark.asyncio
    async def test_invalid_json_returns_empty(self) -> None:
        mock_http = AsyncMock()
        mock_http.get_text = AsyncMock(return_value="not json")
        client = IBGESIDRAClient(http=mock_http)

        result = await client.fetch_table(table_id=5938, variables=[3700])
        assert result == []

    @pytest.mark.asyncio
    async def test_network_error_propagates(self) -> None:
        mock_http = AsyncMock()
        mock_http.get_text = AsyncMock(side_effect=ConnectionError("timeout"))
        client = IBGESIDRAClient(http=mock_http)

        with pytest.raises(ConnectionError, match="timeout"):
            await client.fetch_table(table_id=5938, variables=[3700])

    @pytest.mark.asyncio
    async def test_empty_response(self) -> None:
        mock_http = AsyncMock()
        mock_http.get_text = AsyncMock(return_value="[]")
        client = IBGESIDRAClient(http=mock_http)

        result = await client.fetch_table(table_id=5938, variables=[3700])
        assert result == []

    def test_default_http_client(self) -> None:
        client = IBGESIDRAClient()
        assert client._http is not None

    def test_frozen_dataclass(self) -> None:
        meta = SIDRATableMetadata(id=5938, nome="PIB", universo="Brasil")
        assert meta.id == 5938
        assert meta.nome == "PIB"
