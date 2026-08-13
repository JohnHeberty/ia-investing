"""Unit tests for ia_investing.application.audit_service."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from ia_investing.application.audit_service import (
    AuditService,
    create_domain_audit_entry,
)


@pytest.mark.unit
class TestCreateDomainAuditEntry:
    @pytest.mark.asyncio
    async def test_creates_entry(self):
        mock_session = AsyncMock()
        # Mock advisory lock
        mock_session.execute = AsyncMock()
        # Mock prev hash query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        tenant_id = uuid4()
        entity_id = uuid4()
        entry = await create_domain_audit_entry(
            mock_session,
            tenant_id=tenant_id,
            actor_type="human",
            actor_id="user1",
            action="test.action",
            entity_type="test_entity",
            entity_id=entity_id,
            correlation_id=entity_id,
            details={"key": "value"},
        )
        assert entry.tenant_id == tenant_id
        assert entry.action == "test.action"
        assert entry.hash is not None
        assert entry.hash_prev is None
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_with_prev_hash(self):
        mock_session = AsyncMock()
        prev_hash = "abc123"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = prev_hash
        mock_session.execute = AsyncMock(return_value=mock_result)

        entry = await create_domain_audit_entry(
            mock_session,
            tenant_id=uuid4(),
            actor_type="system",
            actor_id="sys",
            action="test",
            entity_type="e",
            entity_id=uuid4(),
            correlation_id=uuid4(),
        )
        assert entry.hash_prev == prev_hash


@pytest.mark.unit
class TestAuditService:
    @pytest.mark.asyncio
    async def test_log(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = AuditService(mock_session, uuid4())
        entry = await svc.log(
            actor_id=uuid4(),
            action="test.action",
            resource_type="test",
            resource_id=uuid4(),
            changes={"a": 1},
        )
        assert entry.action == "test.action"
        assert entry.hash is not None

    @pytest.mark.asyncio
    async def test_log_with_prev_hash(self):
        mock_session = AsyncMock()
        prev_hash = "prev_hash"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = prev_hash
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = AuditService(mock_session, uuid4())
        entry = await svc.log(
            actor_id=None,
            action="test",
            resource_type="t",
            correlation_id=uuid4(),
        )
        assert entry.hash_prev == prev_hash

    @pytest.mark.asyncio
    async def test_query(self):
        mock_session = AsyncMock()
        mock_rows = MagicMock()
        mock_rows.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_rows)

        svc = AuditService(mock_session, uuid4())
        entries, total = await svc.query()
        assert isinstance(entries, list)

    @pytest.mark.asyncio
    async def test_get_by_id(self):
        mock_session = AsyncMock()
        mock_entry = SimpleNamespace(id=uuid4(), tenant_id=uuid4())
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entry
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = AuditService(mock_session, uuid4())
        result = await svc.get_by_id(uuid4())
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = AuditService(mock_session, uuid4())
        result = await svc.get_by_id(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_chain_valid(self):
        mock_session = AsyncMock()
        now = datetime.now(UTC)
        entries = []
        prev_hash = None
        for i in range(3):
            raw = (prev_hash or "") + now.isoformat() + "human" + "" + f"action{i}" + "t" + "" + "" + "{}" + "{}"
            h = sha256(raw.encode("utf-8")).hexdigest()
            entries.append(SimpleNamespace(
                id=uuid4(), tenant_id=uuid4(), actor_type="human",
                actor_id=None, action=f"action{i}", resource_type="t",
                resource_id=None, correlation_id=None,
                changes=None, meta_data=None,
                hash_prev=prev_hash, hash=h,
                timestamp=now, created_at=now,
            ))
            prev_hash = h
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = entries
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = AuditService(mock_session, uuid4())
        tampered = await svc.verify_chain()
        assert tampered == []

    @pytest.mark.asyncio
    async def test_verify_chain_tampered(self):
        mock_session = AsyncMock()
        now = datetime.now(UTC)
        entry = SimpleNamespace(
            id=uuid4(), tenant_id=uuid4(), actor_type="human",
            actor_id=None, action="test", resource_type="t",
            resource_id=None, correlation_id=None,
            changes=None, meta_data=None,
            hash_prev=None, hash="wrong_hash",
            timestamp=now, created_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [entry]
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = AuditService(mock_session, uuid4())
        tampered = await svc.verify_chain()
        assert len(tampered) > 0
        assert tampered[0]["reason"] == "hash_mismatch"

    @pytest.mark.asyncio
    async def test_get_tamper_evidence(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = AuditService(mock_session, uuid4())
        result = await svc.get_tamper_evidence()
        assert result == []

    @pytest.mark.asyncio
    async def test_query_with_filters(self):
        mock_session = AsyncMock()
        mock_rows = MagicMock()
        mock_rows.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_rows)

        svc = AuditService(mock_session, uuid4())
        entries, total = await svc.query(
            actor_id=uuid4(),
            action="test",
            resource_type="t",
            resource_id=uuid4(),
            from_time=datetime.now(UTC),
            to_time=datetime.now(UTC),
            limit=10,
            offset=5,
        )
        assert isinstance(entries, list)

    @pytest.mark.asyncio
    async def test_verify_chain_with_range(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = AuditService(mock_session, uuid4())
        tampered = await svc.verify_chain(from_id=uuid4(), to_id=uuid4())
        assert tampered == []
