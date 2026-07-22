from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client
from temporalio.contrib.opentelemetry import TracingInterceptor

from apps.api.security import AuthContext, get_auth_context
from ia_investing.application.audit_service import AuditService
from ia_investing.application.operations import OperationService
from ia_investing.database.core import get_async_session
from ia_investing.settings import get_settings

if TYPE_CHECKING:
    from ia_investing.application.committee_service import CommitteeService
    from ia_investing.application.execution_service import ExecutionService

_temporal_client: Client | None = None
_temporal_lock = asyncio.Lock()


async def get_temporal_client() -> Client:
    global _temporal_client
    if _temporal_client is None:
        async with _temporal_lock:
            if _temporal_client is None:
                settings = get_settings()
                _temporal_client = await Client.connect(
                    settings.temporal.address,
                    namespace=settings.temporal.namespace,
                    interceptors=[TracingInterceptor()] if settings.telemetry.enabled else [],
                )
    return _temporal_client


async def get_operation_service(
    session: AsyncSession = Depends(get_async_session),
    temporal_client: Client = Depends(get_temporal_client),
) -> OperationService:
    return OperationService(session, temporal_client)


async def get_audit_service(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> AuditService:
    tenant_id = auth.organization_id if auth.organization_id else UUID(int=0)
    return AuditService(session, tenant_id)


async def get_committee_service(
    session: AsyncSession = Depends(get_async_session),
    audit: AuditService = Depends(get_audit_service),
) -> CommitteeService:
    from ia_investing.application.committee_service import CommitteeService

    return CommitteeService(session, audit)


async def get_execution_service(
    session: AsyncSession = Depends(get_async_session),
    audit: AuditService = Depends(get_audit_service),
) -> ExecutionService:
    from ia_investing.application.execution_service import ExecutionService

    return ExecutionService(session, audit)
