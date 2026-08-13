"""Unit tests for ia_investing.application.instruments — InstrumentMasterService."""

from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ia_investing.application.instruments import (
    AmbiguousInstrumentError,
    InstrumentMasterService,
    InstrumentResolutionV1,
    normalize_alias,
)


@pytest.mark.unit
class TestNormalizeAlias:
    def test_lowercases(self):
        assert normalize_alias("PETR4") == "petr4"

    def test_strips_whitespace(self):
        assert normalize_alias("  Petrobras  ") == "petrobras"

    def test_removes_accents(self):
        assert normalize_alias("São Paulo") == "sao paulo"

    def test_collapses_whitespace(self):
        assert normalize_alias("a  b  c") == "a b c"

    def test_empty(self):
        assert normalize_alias("") == ""


@pytest.mark.unit
class TestInstrumentResolutionV1:
    def test_construction(self):
        r = InstrumentResolutionV1(
            resolution_type="listing",
            issuer_id="00000000-0000-0000-0000-000000000001",
            issuer_name="Petrobras",
            instrument_id="00000000-0000-0000-0000-000000000002",
            listing_id="00000000-0000-0000-0000-000000000003",
            ticker="PETR4",
            as_of=date(2026, 1, 1),
        )
        assert r.resolution_type == "listing"
        assert r.ticker == "PETR4"
        assert r.schema_version == "1.0"

    def test_forbid_extra(self):
        with pytest.raises(Exception):
            InstrumentResolutionV1(
                resolution_type="listing",
                issuer_id="00000000-0000-0000-0000-000000000001",
                issuer_name="X",
                as_of=date(2026, 1, 1),
                extra_field="bad",  # type: ignore[call-arg]
            )


@pytest.mark.unit
class TestInstrumentMasterService:
    @pytest.mark.asyncio
    async def test_resolve_by_ticker(self):
        mock_session = AsyncMock()
        issuer_id = uuid.uuid4()
        instrument_id = uuid.uuid4()
        listing_id = uuid.uuid4()
        mock_listing = SimpleNamespace(
            ticker="PETR4",
            id=listing_id,
            valid_from=date(2020, 1, 1),
            valid_to=None,
        )
        mock_instrument = SimpleNamespace(id=instrument_id)
        mock_issuer = SimpleNamespace(id=issuer_id, name_pt="Petrobras", cnpj="12345678000190")
        mock_result = MagicMock()
        mock_result.all.return_value = [(mock_listing, mock_instrument, mock_issuer)]
        mock_session.execute.return_value = mock_result

        svc = InstrumentMasterService(mock_session)
        result = await svc.resolve("PETR4", date(2026, 1, 1))

        assert result is not None
        assert result.resolution_type == "listing"
        assert result.ticker == "PETR4"
        assert result.issuer_id == issuer_id
        assert result.instrument_id == instrument_id
        assert result.listing_id == listing_id

    @pytest.mark.asyncio
    async def test_resolve_ambiguous_ticker(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        uid = uuid.uuid4()
        mock_result.all.return_value = [
            (SimpleNamespace(ticker="X", id=uid, valid_from=date(2020,1,1), valid_to=None),
             SimpleNamespace(id=uid), SimpleNamespace(id=uid, name_pt="A")),
            (SimpleNamespace(ticker="X", id=uid, valid_from=date(2020,1,1), valid_to=None),
             SimpleNamespace(id=uid), SimpleNamespace(id=uid, name_pt="B")),
        ]
        mock_session.execute.return_value = mock_result

        svc = InstrumentMasterService(mock_session)
        with pytest.raises(AmbiguousInstrumentError):
            await svc.resolve("PETR4", date(2026, 1, 1))

    @pytest.mark.asyncio
    async def test_resolve_not_found(self):
        mock_session = AsyncMock()
        mock_empty = MagicMock()
        mock_empty.all.return_value = []
        mock_empty.scalars.return_value.unique.return_value.all.return_value = []
        mock_session.execute.return_value = mock_empty

        svc = InstrumentMasterService(mock_session)
        result = await svc.resolve("UNKNOWN", date(2026, 1, 1))
        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_by_issuer_name(self):
        mock_session = AsyncMock()
        # No listing or identifier match
        mock_empty = MagicMock()
        mock_empty.all.return_value = []

        issuer_id = uuid.uuid4()
        mock_issuer = SimpleNamespace(id=issuer_id, name_pt="Petrobras")
        mock_issuer_result = MagicMock()
        mock_issuer_result.scalars.return_value.unique.return_value.all.return_value = [mock_issuer]

        mock_session.execute.side_effect = [mock_empty, mock_empty, mock_issuer_result]

        svc = InstrumentMasterService(mock_session)
        result = await svc.resolve("Petrobras", date(2026, 1, 1))
        assert result is not None
        assert result.resolution_type == "issuer"
        assert result.issuer_id == issuer_id
