from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.data_foundation import DataSource, SourceObject, SourceObjectVersion


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def build_storage_key(source_code: str, source_object_id: UUID, content_hash: str) -> str:
    if len(content_hash) != 64 or any(char not in "0123456789abcdef" for char in content_hash):
        raise ValueError("content_hash must be a lowercase SHA-256 digest")
    return f"raw/{source_code.lower()}/{source_object_id}/{content_hash}"


class ImmutableObjectStore(Protocol):
    async def put_once(self, key: str, content: bytes, media_type: str, content_hash: str) -> None: ...


@dataclass(frozen=True, slots=True)
class RawObjectInput:
    source_code: str
    logical_uri: str
    object_type: str
    content: bytes
    media_type: str
    discovered_at: datetime
    published_at: datetime | None = None
    etag: str | None = None
    parser_version: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RawRegistration:
    source_object_id: UUID
    version_id: UUID
    version_number: int
    content_hash: str
    storage_key: str
    created: bool


class RawZoneService:
    def __init__(self, session: AsyncSession, object_store: ImmutableObjectStore) -> None:
        self.session = session
        self.object_store = object_store

    async def register(self, item: RawObjectInput) -> RawRegistration:
        if item.discovered_at.tzinfo is None or (item.published_at and item.published_at.tzinfo is None):
            raise ValueError("raw timestamps must include timezone information")
        source = (
            await self.session.execute(sa.select(DataSource).where(DataSource.code == item.source_code.upper()))
        ).scalar_one_or_none()
        if source is None or not source.is_active:
            raise ValueError(f"unknown or inactive source: {item.source_code}")

        source_object = (
            await self.session.execute(
                sa.select(SourceObject).where(
                    SourceObject.source_id == source.id,
                    SourceObject.logical_uri == item.logical_uri,
                )
            )
        ).scalar_one_or_none()
        if source_object is None:
            source_object = SourceObject(
                source_id=source.id,
                logical_uri=item.logical_uri,
                object_type=item.object_type,
            )
            self.session.add(source_object)
            await self.session.flush()

        digest = sha256_hex(item.content)
        existing = (
            await self.session.execute(
                sa.select(SourceObjectVersion).where(
                    SourceObjectVersion.source_object_id == source_object.id,
                    SourceObjectVersion.content_sha256 == digest,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return RawRegistration(
                source_object.id,
                existing.id,
                existing.version_number,
                digest,
                existing.storage_key,
                False,
            )

        current_version = await self.session.scalar(
            sa.select(sa.func.max(SourceObjectVersion.version_number)).where(
                SourceObjectVersion.source_object_id == source_object.id
            )
        )
        version_number = int(current_version or 0) + 1
        storage_key = build_storage_key(source.code, source_object.id, digest)
        await self.object_store.put_once(storage_key, item.content, item.media_type, digest)
        version = SourceObjectVersion(
            source_object_id=source_object.id,
            version_number=version_number,
            content_sha256=digest,
            storage_key=storage_key,
            etag=item.etag,
            size_bytes=len(item.content),
            media_type=item.media_type,
            published_at=item.published_at,
            discovered_at=item.discovered_at,
            parser_version=item.parser_version,
            metadata_json=item.metadata,
        )
        self.session.add(version)
        await self.session.flush()
        return RawRegistration(source_object.id, version.id, version_number, digest, storage_key, True)


class S3ImmutableObjectStore:
    def __init__(self, client: object, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    async def put_once(self, key: str, content: bytes, media_type: str, content_hash: str) -> None:
        def put() -> None:
            try:
                response = self.client.head_object(Bucket=self.bucket, Key=key)  # type: ignore[attr-defined]
            except self.client.exceptions.ClientError as exc:  # type: ignore[attr-defined]
                if exc.response.get("Error", {}).get("Code") not in {"404", "NoSuchKey", "NotFound"}:
                    raise
            else:
                stored_hash = response.get("Metadata", {}).get("sha256")
                if stored_hash != content_hash or response.get("ContentLength") != len(content):
                    raise RuntimeError("immutable object key already contains different content")
                return
            self.client.put_object(  # type: ignore[attr-defined]
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType=media_type,
                Metadata={"sha256": content_hash},
            )

        await asyncio.to_thread(put)
