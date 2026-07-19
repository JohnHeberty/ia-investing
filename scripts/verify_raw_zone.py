"""Exercise Raw Zone persistence against the local PostgreSQL and MinIO stack."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import boto3

from database.core import session_scope
from ia_investing.data.raw_zone import RawObjectInput, RawZoneService, S3ImmutableObjectStore
from ia_investing.settings import get_settings


async def main() -> None:
    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.storage.endpoint,
        aws_access_key_id=settings.storage.access_key.get_secret_value(),
        aws_secret_access_key=settings.storage.secret_key.get_secret_value(),
        region_name="us-east-1",
    )
    store = S3ImmutableObjectStore(client, settings.storage.bucket)
    base = RawObjectInput(
        source_code="CVM",
        logical_uri=f"fixture://cvm/dfp/phase-2-verification/{uuid4()}.csv",
        object_type="DFP",
        content=b"CD_CONTA;VL_CONTA\n3.01;100.00\n",
        media_type="text/csv",
        discovered_at=datetime(2026, 7, 18, 12, tzinfo=UTC),
        parser_version="fixture-v1",
        metadata={"fixture": True},
    )
    async with session_scope() as session:
        first = await RawZoneService(session, store).register(base)
    async with session_scope() as session:
        repeated = await RawZoneService(session, store).register(base)
    changed = RawObjectInput(
        source_code=base.source_code,
        logical_uri=base.logical_uri,
        object_type=base.object_type,
        content=base.content + b"3.02;-20.00\n",
        media_type=base.media_type,
        discovered_at=datetime(2026, 7, 18, 13, tzinfo=UTC),
        parser_version="fixture-v1",
        metadata=base.metadata,
    )
    async with session_scope() as session:
        second = await RawZoneService(session, store).register(changed)

    assert repeated.version_id == first.version_id and not repeated.created
    assert second.source_object_id == first.source_object_id
    assert second.version_number == first.version_number + 1 and second.created
    stored = client.head_object(Bucket=settings.storage.bucket, Key=first.storage_key)
    assert stored["Metadata"]["sha256"] == first.content_hash
    print(
        f"raw-zone-ok object={first.source_object_id} "
        f"versions={first.version_number},{second.version_number} idempotent=true"
    )


if __name__ == "__main__":
    asyncio.run(main())
