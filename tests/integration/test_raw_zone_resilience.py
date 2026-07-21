"""Integration tests: retry, crash recovery, and concurrency for RawZone.

Requires real PostgreSQL + MinIO:
    docker compose --profile test up -d --wait
    pytest tests/integration/test_raw_zone_resilience.py -x -v
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database.models.data_foundation import DataSource, SourceObject, SourceObjectVersion
from ia_investing.data.raw_zone import RawObjectInput, RawRegistration, RawZoneService, S3ImmutableObjectStore

_TZ = UTC
_SOURCE_CODE = "data-steward-cvm"


def _dt(y: int, m: int, d: int, h: int = 0, mi: int = 0) -> datetime:
    return datetime(y, m, d, h, mi, tzinfo=_TZ)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _make_item(
    logical_uri: str,
    content: bytes,
    *,
    suffix: str = "",
) -> RawObjectInput:
    return RawObjectInput(
        source_code=_SOURCE_CODE,
        logical_uri=logical_uri,
        object_type="financial_statement",
        content=content,
        media_type="application/xml",
        discovered_at=_dt(2026, 7, 20, 10, 0),
    )


async def _require_source(session: AsyncSession) -> None:
    stmt = sa.select(DataSource).where(DataSource.code == _SOURCE_CODE)
    ds = (await session.execute(stmt)).scalar_one_or_none()
    if ds is None:
        pytest.skip("CVM data source not seeded — run migrations first")


# ---------------------------------------------------------------------------
# 1. Retry after S3 failure — real DB, S3 fails once then succeeds
# ---------------------------------------------------------------------------


class _FailingOnceStore:
    """Wraps real S3ImmutableObjectStore; fails on first put_once then delegates."""

    def __init__(self, real_store: S3ImmutableObjectStore) -> None:
        self._real = real_store
        self._attempts: list[str] = []

    async def put_once(self, key: str, content: bytes, media_type: str, content_hash: str) -> None:
        self._attempts.append(key)
        if len(self._attempts) == 1:
            raise ConnectionError("simulated S3 timeout on first attempt")
        await self._real.put_once(key, content, media_type, content_hash)


@pytest.mark.asyncio
async def test_retry_after_s3_failure_succeeds(
    session: AsyncSession,
    minio_client,
) -> None:
    """S3 write fails on first attempt; retry succeeds and creates version."""
    await _require_source(session)

    real_store = S3ImmutableObjectStore(minio_client, "raw-documents")
    failing_store = _FailingOnceStore(real_store)
    svc = RawZoneService(session, failing_store)

    item = _make_item(
        "cvm://dfp/retry-test/2026",
        b"<xml>retry content</xml>",
    )

    with pytest.raises(ConnectionError, match="simulated S3 timeout"):
        await svc.register(item)

    assert len(failing_store._attempts) == 1

    # Retry with the same service — second put_once succeeds
    result = await svc.register(item)
    assert result.created is True
    assert len(failing_store._attempts) == 2

    # Verify persisted in DB
    version = (
        await session.execute(sa.select(SourceObjectVersion).where(SourceObjectVersion.id == result.version_id))
    ).scalar_one()
    assert version.content_sha256 == _sha256(item.content)
    assert version.size_bytes == len(item.content)

    # Verify content in S3
    obj = minio_client.get_object(Bucket="raw-documents", Key=version.storage_key)
    assert obj["Body"].read() == item.content
    await session.commit()


# ---------------------------------------------------------------------------
# 2. Concurrent duplicate registration — race condition
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_duplicate_registration(
    session: AsyncSession,
    engine,
    minio_client,
) -> None:
    """Two concurrent registrations with same content — DB unique constraint protects integrity."""
    await _require_source(session)

    real_store = S3ImmutableObjectStore(minio_client, "raw-documents")
    content = b"<xml>concurrent content</xml>"
    item = _make_item("cvm://dfp/concurrent-test/2026", content)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore[arg-type]

    async def _register() -> RawRegistration:
        async with factory() as s:
            svc = RawZoneService(s, real_store)
            return await svc.register(item)

    results: list[RawRegistration | BaseException] = list(
        await asyncio.gather(
            _register(),
            _register(),
            return_exceptions=True,
        )
    )

    successes = [r for r in results if isinstance(r, RawRegistration)]

    # At least one should succeed; the other may fail with IntegrityError
    # due to unique constraint on (source_object_id, content_sha256)
    assert len(successes) >= 1

    if len(successes) == 2:
        # If both succeeded, both should return the same version_id (dedup)
        assert successes[0].version_id == successes[1].version_id
        assert successes[0].created is True or successes[1].created is True

    # Verify exactly one version exists for this content
    digest = _sha256(content)
    count = await session.scalar(
        sa.select(sa.func.count(SourceObjectVersion.id)).where(SourceObjectVersion.content_sha256 == digest)
    )
    assert count == 1
    await session.commit()


# ---------------------------------------------------------------------------
# 3. S3 content-addressed dedup — same hash, no redundant storage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_s3_content_addressed_dedup(
    session: AsyncSession,
    minio_client,
) -> None:
    """S3 put_once is idempotent — same key+hash doesn't overwrite."""
    await _require_source(session)

    real_store = S3ImmutableObjectStore(minio_client, "raw-documents")
    svc = RawZoneService(session, real_store)

    content = b"<xml>s3 dedup content</xml>"
    item = _make_item("cvm://dfp/s3-dedup-test/2026", content)

    r1 = await svc.register(item)
    assert r1.created is True

    # put_once again with same content — should be a no-op on S3
    await real_store.put_once(r1.storage_key, item.content, "application/xml", _sha256(content))

    # DB dedup returns same version
    r2 = await svc.register(item)
    assert r2.created is False
    assert r2.version_id == r1.version_id
    await session.commit()


# ---------------------------------------------------------------------------
# 4. Orphaned S3 object — S3 has object, DB doesn't (simulates crash recovery)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orphaned_s3_object_handled_on_retry(
    session: AsyncSession,
    minio_client,
) -> None:
    """Object exists in S3 but not in DB (crash between put_once and DB commit).
    Retry creates a new version and re-uploads (put_once is idempotent).
    """
    await _require_source(session)

    real_store = S3ImmutableObjectStore(minio_client, "raw-documents")
    svc = RawZoneService(session, real_store)

    content = b"<xml>orphaned object test</xml>"
    item = _make_item("cvm://dfp/orphan-test/2026", content)

    # First: register normally to get the storage key
    r1 = await svc.register(item)
    assert r1.created is True

    # Delete from DB but keep in S3 (simulates crash after put_once, before commit)
    await session.delete(
        (
            await session.execute(sa.select(SourceObjectVersion).where(SourceObjectVersion.id == r1.version_id))
        ).scalar_one()
    )
    await session.flush()

    # Also delete the SourceObject so we get a fresh one
    source_obj = (
        await session.execute(sa.select(SourceObject).where(SourceObject.id == r1.source_object_id))
    ).scalar_one()
    await session.delete(source_obj)
    await session.flush()

    # Retry — should create a new SourceObject and version
    r2 = await svc.register(item)
    assert r2.created is True
    assert r2.source_object_id != r1.source_object_id

    # Verify version points to same S3 content
    version = (
        await session.execute(sa.select(SourceObjectVersion).where(SourceObjectVersion.id == r2.version_id))
    ).scalar_one()
    assert version.content_sha256 == _sha256(content)

    # Verify content readable from S3
    obj = minio_client.get_object(Bucket="raw-documents", Key=version.storage_key)
    assert obj["Body"].read() == content
    await session.commit()


# ---------------------------------------------------------------------------
# 5. Full round-trip — different content creates new version
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_different_content_creates_new_version(
    session: AsyncSession,
    minio_client,
) -> None:
    """Registering different content to same logical_uri creates version 2."""
    await _require_source(session)

    real_store = S3ImmutableObjectStore(minio_client, "raw-documents")
    svc = RawZoneService(session, real_store)

    item_v1 = _make_item("cvm://dfp/versioning-test/2026", b"<xml>version 1</xml>")
    item_v2 = _make_item("cvm://dfp/versioning-test/2026", b"<xml>version 2</xml>")

    r1 = await svc.register(item_v1)
    assert r1.created is True
    assert r1.version_number == 1

    r2 = await svc.register(item_v2)
    assert r2.created is True
    assert r2.version_number == 2
    assert r2.version_id != r1.version_id

    # Both versions exist in DB
    count = await session.scalar(
        sa.select(sa.func.count(SourceObjectVersion.id)).where(
            SourceObjectVersion.source_object_id == r1.source_object_id
        )
    )
    assert count == 2

    # Both objects readable from S3
    v1 = (
        await session.execute(sa.select(SourceObjectVersion).where(SourceObjectVersion.id == r1.version_id))
    ).scalar_one()
    v2 = (
        await session.execute(sa.select(SourceObjectVersion).where(SourceObjectVersion.id == r2.version_id))
    ).scalar_one()

    obj1 = minio_client.get_object(Bucket="raw-documents", Key=v1.storage_key)
    assert obj1["Body"].read() == item_v1.content

    obj2 = minio_client.get_object(Bucket="raw-documents", Key=v2.storage_key)
    assert obj2["Body"].read() == item_v2.content
    await session.commit()
