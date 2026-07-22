from __future__ import annotations

import asyncio

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client
from temporalio.contrib.opentelemetry import TracingInterceptor

from ia_investing.application.operations import OperationService
from ia_investing.database.core import get_async_session
from ia_investing.settings import get_settings

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
