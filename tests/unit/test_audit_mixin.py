from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import structlog.contextvars

from ia_investing.application._audit_mixin import AuditMixin


@pytest.fixture(autouse=True)
def _clear_contextvars() -> None:
    structlog.contextvars.clear_contextvars()
    yield
    structlog.contextvars.clear_contextvars()


class TestAuditMixin:
    @pytest.mark.asyncio
    async def test_calls_audit_service_log(self) -> None:
        mixin = AuditMixin()
        session = AsyncMock()
        tenant_id = uuid4()
        actor_id = uuid4()
        resource_id = uuid4()

        with patch("ia_investing.application._audit_mixin.AuditService") as MockAudit:
            mock_svc = MagicMock()
            mock_svc.log = AsyncMock()
            MockAudit.return_value = mock_svc

            await mixin._audit(
                session=session,
                tenant_id=tenant_id,
                actor_id=actor_id,
                action="create",
                resource_type="portfolio",
                resource_id=resource_id,
                changes={"name": "new"},
                metadata={"extra": True},
            )

            MockAudit.assert_called_once_with(session, tenant_id)
            mock_svc.log.assert_called_once()
            call_kwargs = mock_svc.log.call_args[1]
            assert call_kwargs["actor_id"] == actor_id
            assert call_kwargs["action"] == "create"
            assert call_kwargs["resource_type"] == "portfolio"
            assert call_kwargs["resource_id"] == resource_id
            assert call_kwargs["changes"] == {"name": "new"}

    @pytest.mark.asyncio
    async def test_merges_structlog_context_into_metadata(self) -> None:
        mixin = AuditMixin()
        session = AsyncMock()
        tenant_id = uuid4()

        structlog.contextvars.bind_contextvars(
            request_id="req-abc",
            trace_id="trace-xyz",
            ip="192.168.1.1",
            user_agent="TestAgent/1.0",
        )

        with patch("ia_investing.application._audit_mixin.AuditService") as MockAudit:
            mock_svc = MagicMock()
            mock_svc.log = AsyncMock()
            MockAudit.return_value = mock_svc

            await mixin._audit(
                session=session,
                tenant_id=tenant_id,
                actor_id=None,
                action="view",
                resource_type="portfolio",
            )

            call_kwargs = mock_svc.log.call_args[1]
            meta = call_kwargs["metadata"]
            assert meta["request_id"] == "req-abc"
            assert meta["trace_id"] == "trace-xyz"
            assert meta["ip"] == "192.168.1.1"
            assert meta["user_agent"] == "TestAgent/1.0"

    @pytest.mark.asyncio
    async def test_preserves_existing_metadata(self) -> None:
        mixin = AuditMixin()
        session = AsyncMock()
        tenant_id = uuid4()

        with patch("ia_investing.application._audit_mixin.AuditService") as MockAudit:
            mock_svc = MagicMock()
            mock_svc.log = AsyncMock()
            MockAudit.return_value = mock_svc

            await mixin._audit(
                session=session,
                tenant_id=tenant_id,
                actor_id=None,
                action="update",
                resource_type="instrument",
                metadata={"custom_key": "custom_value"},
            )

            call_kwargs = mock_svc.log.call_args[1]
            assert call_kwargs["metadata"]["custom_key"] == "custom_value"

    @pytest.mark.asyncio
    async def test_none_metadata_initializes_empty_dict(self) -> None:
        mixin = AuditMixin()
        session = AsyncMock()
        tenant_id = uuid4()

        with patch("ia_investing.application._audit_mixin.AuditService") as MockAudit:
            mock_svc = MagicMock()
            mock_svc.log = AsyncMock()
            MockAudit.return_value = mock_svc

            await mixin._audit(
                session=session,
                tenant_id=tenant_id,
                actor_id=None,
                action="delete",
                resource_type="thesis",
            )

            call_kwargs = mock_svc.log.call_args[1]
            assert isinstance(call_kwargs["metadata"], dict)

    @pytest.mark.asyncio
    async def test_omits_none_context_values_from_metadata(self) -> None:
        mixin = AuditMixin()
        session = AsyncMock()
        tenant_id = uuid4()

        with patch("ia_investing.application._audit_mixin.AuditService") as MockAudit:
            mock_svc = MagicMock()
            mock_svc.log = AsyncMock()
            MockAudit.return_value = mock_svc

            await mixin._audit(
                session=session,
                tenant_id=tenant_id,
                actor_id=None,
                action="view",
                resource_type="scorecard",
            )

            call_kwargs = mock_svc.log.call_args[1]
            meta = call_kwargs["metadata"]
            assert "request_id" not in meta
            assert "ip" not in meta
            assert "duration_ms" not in meta
