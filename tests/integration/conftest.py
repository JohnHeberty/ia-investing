"""Shared fixtures for integration tests.

Skips all tests in tests/integration/ when PostgreSQL or MinIO are unreachable.
Set DATABASE__URL and STORAGE__* env vars to target a running instance.

Usage:
    docker compose --profile test up -d --wait
    pytest tests/integration/ -x -v
"""

from __future__ import annotations

import os
import socket
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DB_URL = os.getenv(
    "DATABASE__URL",
    "postgresql+asyncpg://app:app-local-only@localhost:5432/stock_intelligence",
)

MINIO_ENDPOINT = os.getenv("STORAGE__ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("STORAGE__ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("STORAGE__SECRET_KEY", "minio-local-only")
MINIO_BUCKET = os.getenv("STORAGE__BUCKET", "raw-documents")

TZ = UTC


# ---------------------------------------------------------------------------
# Port-reachability helpers
# ---------------------------------------------------------------------------


def _host_port_reachable(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


def _postgres_reachable() -> bool:
    parsed = urlparse(DB_URL.replace("+asyncpg", "+psycopg"))
    return _host_port_reachable(parsed.hostname or "localhost", parsed.port or 5432)


def _minio_reachable() -> bool:
    parsed = urlparse(MINIO_ENDPOINT)
    return _host_port_reachable(parsed.hostname or "localhost", parsed.port or 9000)


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _postgres_reachable(),
        reason="PostgreSQL not reachable — start with: docker compose --profile test up -d",
    ),
]


# ---------------------------------------------------------------------------
# Session-scoped engine
# ---------------------------------------------------------------------------

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(DB_URL, pool_size=5, max_overflow=5)
    return _engine


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = _get_engine()
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as sess:
        yield sess
        await sess.rollback()


# ---------------------------------------------------------------------------
# MinIO
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def minio_client():
    if not _minio_reachable():
        pytest.skip("MinIO not reachable — start with: docker compose --profile test up -d")
    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name="us-east-1",
    )
    yield client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dt(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=TZ)
