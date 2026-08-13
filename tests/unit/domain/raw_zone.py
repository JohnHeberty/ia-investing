"""Unit tests for ia_investing.data.raw_zone — RawZoneService."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ia_investing.data.raw_zone import (
    RawObjectInput,
    RawRegistration,
    RawZoneService,
    build_storage_key,
    sha256_hex,
)


@pytest.mark.unit
class TestSha256Hex:
    def test_basic(self):
        result = sha256_hex(b"hello")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self):
        assert sha256_hex(b"test") == sha256_hex(b"test")

    def test_different_input(self):
        assert sha256_hex(b"a") != sha256_hex(b"b")


@pytest.mark.unit
class TestBuildStorageKey:
    def test_valid(self):
        oid = uuid4()
        key = build_storage_key("CVM", oid, "a" * 64)
        assert key.startswith("raw/cvm/")
        assert str(oid) in key

    def test_invalid_hash_short(self):
        with pytest.raises(ValueError, match="content_hash"):
            build_storage_key("CVM", uuid4(), "abc")

    def test_invalid_hash_uppercase(self):
        with pytest.raises(ValueError, match="content_hash"):
            build_storage_key("CVM", uuid4(), "A" * 64)


@pytest.mark.unit
class TestRawZoneService:
    @pytest.mark.asyncio
    async def test_register_new_object(self):
        mock_session = AsyncMock()
        mock_store = AsyncMock()

        # Mock source lookup
        mock_source = SimpleNamespace(id=uuid4(), code="CVM", is_active=True)
        mock_source_result = MagicMock()
        mock_source_result.scalar_one_or_none.return_value = mock_source

        # Mock no existing source object
        mock_so_result = MagicMock()
        mock_so_result.scalar_one_or_none.return_value = None

        # Mock no existing version
        mock_ver_result = MagicMock()
        mock_ver_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [mock_source_result, mock_so_result, mock_ver_result]
        mock_session.scalar.return_value = None  # max version

        item = RawObjectInput(
            source_code="CVM",
            logical_uri="cvm://test",
            object_type="filing",
            content=b"test content",
            media_type="text/xml",
            discovered_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        svc = RawZoneService(mock_session, mock_store)
        result = await svc.register(item)
        assert result.created is True
        mock_store.put_once.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_duplicate_returns_existing(self):
        mock_session = AsyncMock()
        mock_store = AsyncMock()

        mock_source = SimpleNamespace(id=uuid4(), code="CVM", is_active=True)
        mock_source_result = MagicMock()
        mock_source_result.scalar_one_or_none.return_value = mock_source

        mock_so = SimpleNamespace(id=uuid4())
        mock_so_result = MagicMock()
        mock_so_result.scalar_one_or_none.return_value = mock_so

        mock_existing_ver = SimpleNamespace(id=uuid4(), version_number=1, storage_key="existing/key")
        mock_ver_result = MagicMock()
        mock_ver_result.scalar_one_or_none.return_value = mock_existing_ver

        mock_session.execute.side_effect = [mock_source_result, mock_so_result, mock_ver_result]

        item = RawObjectInput(
            source_code="CVM",
            logical_uri="cvm://test",
            object_type="filing",
            content=b"test",
            media_type="text/xml",
            discovered_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        svc = RawZoneService(mock_session, mock_store)
        result = await svc.register(item)
        assert result.created is False
        mock_store.put_once.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_unknown_source_raises(self):
        mock_session = AsyncMock()
        mock_store = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        item = RawObjectInput(
            source_code="UNKNOWN",
            logical_uri="x://y",
            object_type="filing",
            content=b"data",
            media_type="text/xml",
            discovered_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        svc = RawZoneService(mock_session, mock_store)
        with pytest.raises(ValueError, match="unknown or inactive"):
            await svc.register(item)

    @pytest.mark.asyncio
    async def test_register_naive_timestamp_raises(self):
        mock_session = AsyncMock()
        mock_store = AsyncMock()

        item = RawObjectInput(
            source_code="CVM",
            logical_uri="x://y",
            object_type="filing",
            content=b"data",
            media_type="text/xml",
            discovered_at=datetime(2026, 1, 1),  # no tzinfo
        )

        svc = RawZoneService(mock_session, mock_store)
        with pytest.raises(ValueError, match="timezone"):
            await svc.register(item)
