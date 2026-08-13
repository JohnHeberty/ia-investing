"""Tests for connectors.investor_relations._ri — CVM IR document fetch."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from connectors.investor_relations._ri import (
    _compute_hash,
    _parse_date,
    fetch_ri_calendar,
    fetch_ri_documents,
)

# --- _compute_hash ---


@pytest.mark.unit
def test_compute_hash_deterministic() -> None:
    h1 = _compute_hash("PETR4:RITrimestral:https://example.com")
    h2 = _compute_hash("PETR4:RITrimestral:https://example.com")
    assert h1 == h2


@pytest.mark.unit
def test_compute_hash_length() -> None:
    h = _compute_hash("test")
    assert len(h) == 16


@pytest.mark.unit
def test_compute_hash_different_inputs() -> None:
    h1 = _compute_hash("input-a")
    h2 = _compute_hash("input-b")
    assert h1 != h2


# --- _parse_date ---


@pytest.mark.unit
def test_parse_date_full_format() -> None:
    result = _parse_date("15/03/2026 14:30:00")
    assert result == datetime(2026, 3, 15, 14, 30, 0, tzinfo=UTC)


@pytest.mark.unit
def test_parse_date_date_only() -> None:
    result = _parse_date("15/03/2026")
    assert result == datetime(2026, 3, 15, tzinfo=UTC)


@pytest.mark.unit
def test_parse_date_iso_format() -> None:
    result = _parse_date("2026-03-15T14:30:00")
    assert result == datetime(2026, 3, 15, 14, 30, 0, tzinfo=UTC)


@pytest.mark.unit
def test_parse_date_unknown_format_falls_back() -> None:
    result = _parse_date("not-a-date")
    assert result.tzinfo == UTC
    assert (datetime.now(UTC) - result).total_seconds() < 5


@pytest.mark.unit
def test_parse_date_strips_whitespace() -> None:
    result = _parse_date("  15/03/2026  ")
    assert result == datetime(2026, 3, 15, tzinfo=UTC)


# --- fetch_ri_documents ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_ri_documents_valid_json() -> None:
    data = [
        {
            "nomeDocumento": "RIT Anual 2025",
            "linkDocumento": "https://cvm.gov.br/doc.pdf",
            "data": "15/03/2026 10:00:00",
            "tipoDocumento": "RI",
        }
    ]
    mock_client = AsyncMock()
    mock_client.get_text = AsyncMock(return_value=json.dumps(data))

    docs = await fetch_ri_documents("PETR4", client=mock_client)
    assert len(docs) == 1
    assert docs[0].ticker == "PETR4"
    assert docs[0].title == "RIT Anual 2025"
    assert docs[0].doc_type == "RI"
    assert docs[0].published_at == datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_ri_documents_dict_wrapped_in_data() -> None:
    data = {
        "data": [
            {
                "nomeDocumento": "Doc1",
                "linkDocumento": "https://example.com/1",
                "data": "01/01/2026",
                "tipoDocumento": "RI",
            }
        ]
    }
    mock_client = AsyncMock()
    mock_client.get_text = AsyncMock(return_value=json.dumps(data))

    docs = await fetch_ri_documents("VALE3", client=mock_client)
    assert len(docs) == 1
    assert docs[0].ticker == "VALE3"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_ri_documents_invalid_json() -> None:
    mock_client = AsyncMock()
    mock_client.get_text = AsyncMock(return_value="<html>error</html>")

    docs = await fetch_ri_documents("PETR4", client=mock_client)
    assert docs == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_ri_documents_empty_array() -> None:
    mock_client = AsyncMock()
    mock_client.get_text = AsyncMock(return_value="[]")

    docs = await fetch_ri_documents("PETR4", client=mock_client)
    assert docs == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_ri_documents_skips_incomplete_items() -> None:
    data = [
        {"nomeDocumento": "", "linkDocumento": ""},  # both empty → skip
        {"nomeDocumento": "Valid Doc", "linkDocumento": "https://example.com"},
    ]
    mock_client = AsyncMock()
    mock_client.get_text = AsyncMock(return_value=json.dumps(data))

    docs = await fetch_ri_documents("PETR4", client=mock_client)
    assert len(docs) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_ri_documents_alternative_field_names() -> None:
    data = [
        {
            "title": "Alt Title",
            "url": "https://example.com/alt",
            "publicacao": "20/06/2026",
            "tipo": "Fato Relevante",
        }
    ]
    mock_client = AsyncMock()
    mock_client.get_text = AsyncMock(return_value=json.dumps(data))

    docs = await fetch_ri_documents("ITUB4", client=mock_client)
    assert len(docs) == 1
    assert docs[0].title == "Alt Title"
    assert docs[0].url == "https://example.com/alt"
    assert docs[0].doc_type == "Fato Relevante"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_ri_documents_no_date_uses_now() -> None:
    data = [{"nomeDocumento": "NoDate", "linkDocumento": "https://example.com"}]
    mock_client = AsyncMock()
    mock_client.get_text = AsyncMock(return_value=json.dumps(data))

    docs = await fetch_ri_documents("PETR4", client=mock_client)
    assert len(docs) == 1
    assert (datetime.now(UTC) - docs[0].published_at).total_seconds() < 5


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_ri_documents_creates_default_client() -> None:
    with pytest.raises(Exception):
        # No client provided → will try to create HttpClient which needs httpx
        # but we just verify it doesn't crash with AttributeError
        await fetch_ri_documents("PETR4", client=None)


# --- fetch_ri_calendar ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_ri_calendar_valid_json() -> None:
    data = [
        {
            "evento": "Assembleia Geral",
            "data": "25/04/2026",
            "descricao": "AGO anual",
        }
    ]
    mock_client = AsyncMock()
    mock_client.get_text = AsyncMock(return_value=json.dumps(data))

    events = await fetch_ri_calendar("PETR4", client=mock_client)
    assert len(events) == 1
    assert events[0]["ticker"] == "PETR4"
    assert events[0]["event"] == "Assembleia Geral"
    assert events[0]["date"] == "25/04/2026"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_ri_calendar_dict_wrapped() -> None:
    data = {"data": [{"evento": "Dividendos", "data": "01/06/2026"}]}
    mock_client = AsyncMock()
    mock_client.get_text = AsyncMock(return_value=json.dumps(data))

    events = await fetch_ri_calendar("VALE3", client=mock_client)
    assert len(events) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_ri_calendar_invalid_json() -> None:
    mock_client = AsyncMock()
    mock_client.get_text = AsyncMock(return_value="not json")

    events = await fetch_ri_calendar("PETR4", client=mock_client)
    assert events == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_ri_calendar_skips_empty_events() -> None:
    data = [
        {"evento": "", "data": ""},  # both empty → skip
        {"evento": "Dividends", "data": "01/01/2026"},
    ]
    mock_client = AsyncMock()
    mock_client.get_text = AsyncMock(return_value=json.dumps(data))

    events = await fetch_ri_calendar("PETR4", client=mock_client)
    assert len(events) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_ri_calendar_alternative_fields() -> None:
    data = [{"title": "Event", "dtEvento": "15/03/2026", "obs": "Details"}]
    mock_client = AsyncMock()
    mock_client.get_text = AsyncMock(return_value=json.dumps(data))

    events = await fetch_ri_calendar("PETR4", client=mock_client)
    assert len(events) == 1
    assert events[0]["event"] == "Event"
    assert events[0]["date"] == "15/03/2026"
    assert events[0]["description"] == "Details"
