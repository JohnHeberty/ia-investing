"""Tests for apps.api.dependencies — service factories and Temporal client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from apps.api.dependencies import (
    get_audit_service,
    get_committee_service,
    get_execution_service,
    get_operation_service,
    get_temporal_client,
)
from apps.api.security import AuthContext


@pytest.fixture()
def mock_session() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def mock_auth_org() -> AuthContext:
    return AuthContext(
        subject="user-1",
        permissions=frozenset({"portfolio:read"}),
        authentication_method="oidc",
        organization_id=uuid4(),
    )


@pytest.fixture()
def mock_auth_no_org() -> AuthContext:
    return AuthContext(
        subject="user-2",
        permissions=frozenset(),
        authentication_method="oidc",
        organization_id=None,
    )


class TestGetTemporalClient:
    @pytest.mark.asyncio
    async def test_returns_client(self) -> None:
        mock_client = AsyncMock()
        mock_settings = MagicMock()
        mock_settings.temporal.address = "localhost:7233"
        mock_settings.temporal.namespace = "default"
        mock_settings.telemetry.enabled = False

        with patch("apps.api.dependencies.get_settings", return_value=mock_settings):
            import apps.api.dependencies as deps
            deps._temporal_client = None
            with patch("apps.api.dependencies.Client") as MockClient:
                MockClient.connect = AsyncMock(return_value=mock_client)
                result = await get_temporal_client()
                assert result is mock_client

    @pytest.mark.asyncio
    async def test_caches_client(self) -> None:
        mock_client = AsyncMock()
        import apps.api.dependencies as deps
        deps._temporal_client = mock_client
        result = await get_temporal_client()
        assert result is mock_client
        deps._temporal_client = None


class TestGetOperationService:
    @pytest.mark.asyncio
    async def test_returns_service(self) -> None:
        mock_temporal = AsyncMock()
        mock_session = MagicMock()
        with patch("apps.api.dependencies.get_async_session", return_value=mock_session):
            with patch("apps.api.dependencies.get_temporal_client", new_callable=AsyncMock, return_value=mock_temporal):
                result = await get_operation_service(session=mock_session, temporal_client=mock_temporal)
                assert result is not None


class TestGetAuditService:
    @pytest.mark.asyncio
    async def test_returns_service_with_org(self, mock_session: MagicMock, mock_auth_org: AuthContext) -> None:
        result = await get_audit_service(session=mock_session, auth=mock_auth_org)
        assert result is not None

    @pytest.mark.asyncio
    async def test_raises_403_without_org(self, mock_session: MagicMock, mock_auth_no_org: AuthContext) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await get_audit_service(session=mock_session, auth=mock_auth_no_org)
        assert exc_info.value.status_code == 403
        assert "organization context is required" in exc_info.value.detail


class TestGetCommitteeService:
    @pytest.mark.asyncio
    async def test_returns_service(self, mock_session: MagicMock, mock_auth_org: AuthContext) -> None:
        result = await get_committee_service(session=mock_session, auth=mock_auth_org)
        assert result is not None


class TestGetExecutionService:
    @pytest.mark.asyncio
    async def test_returns_service(self, mock_session: MagicMock, mock_auth_org: AuthContext) -> None:
        mock_audit = MagicMock()
        result = await get_execution_service(session=mock_session, audit=mock_audit)
        assert result is not None
