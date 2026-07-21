"""Integration test: MinIO raw zone round-trip.

Verifies:
  - S3ImmutableObjectStore.put_once writes objects
  - Content-addressed keys prevent duplicate storage
  - RawZoneService.register creates SourceObject + version in DB
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.data_foundation import DataSource, SourceObjectVersion
from ia_investing.data.raw_zone import RawObjectInput, RawZoneService, S3ImmutableObjectStore

_TZ = UTC


def _dt(y: int, m: int, d: int, h: int = 0, mi: int = 0) -> datetime:
    return datetime(y, m, d, h, mi, tzinfo=_TZ)


@pytest.mark.asyncio
async def test_raw_zone_register_creates_version(session: AsyncSession, minio_client) -> None:
    """register() creates SourceObject and SourceObjectVersion in DB."""
    stmt = sa.select(DataSource).where(DataSource.code == "data-steward-cvm")
    ds = (await session.execute(stmt)).scalar_one_or_none()
    if ds is None:
        pytest.skip("CVM data source not seeded — run migrations first")

    store = S3ImmutableObjectStore(minio_client, "raw-documents")
    svc = RawZoneService(session, store)

    item = RawObjectInput(
        source_code="data-steward-cvm",
        logical_uri="cvm://dfp/PETROBRAS/2024",
        object_type="financial_statement",
        content=b"<xml>test content</xml>",
        media_type="application/xml",
        discovered_at=_dt(2025, 1, 15, 10, 0),
        published_at=_dt(2024, 12, 31),
    )
    result = await svc.register(item)
    assert result.created is True
    assert result.version_number == 1
    assert len(result.content_hash) == 64

    db_version = (
        await session.execute(sa.select(SourceObjectVersion).where(SourceObjectVersion.id == result.version_id))
    ).scalar_one()
    assert db_version.storage_key.startswith("raw/data-steward-cvm/")
    assert db_version.size_bytes == len(item.content)
    await session.commit()


@pytest.mark.asyncio
async def test_raw_zone_dedup_by_hash(session: AsyncSession, minio_client) -> None:
    """register() with same content returns created=False."""
    stmt = sa.select(DataSource).where(DataSource.code == "data-steward-cvm")
    ds = (await session.execute(stmt)).scalar_one_or_none()
    if ds is None:
        pytest.skip("CVM data source not seeded")

    store = S3ImmutableObjectStore(minio_client, "raw-documents")
    svc = RawZoneService(session, store)

    item = RawObjectInput(
        source_code="data-steward-cvm",
        logical_uri="cvm://dfp/VALE/2024",
        object_type="financial_statement",
        content=b"<xml>duplicate content test</xml>",
        media_type="application/xml",
        discovered_at=_dt(2025, 2, 1, 10, 0),
    )
    r1 = await svc.register(item)
    assert r1.created is True

    r2 = await svc.register(item)
    assert r2.created is False
    assert r2.version_id == r1.version_id
    await session.commit()
