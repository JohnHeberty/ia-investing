from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class SourceLicense(Base):
    __tablename__ = "source_licenses"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(sa.String(50), unique=True)
    name: Mapped[str] = mapped_column(sa.String(200))
    terms_url: Mapped[str | None] = mapped_column(sa.Text)
    permits_redistribution: Mapped[bool] = mapped_column(default=False)
    retention_days: Mapped[int | None]
    reviewed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(sa.String(50), unique=True)
    name: Mapped[str] = mapped_column(sa.String(200))
    base_url: Mapped[str] = mapped_column(sa.Text)
    owner_role: Mapped[str] = mapped_column(sa.String(100))
    credential_reference: Mapped[str | None] = mapped_column(sa.String(300))
    schema_version: Mapped[str] = mapped_column(sa.String(50))
    rate_limit_per_minute: Mapped[int | None]
    license_id: Mapped[UUID] = mapped_column(sa.ForeignKey("source_licenses.id", ondelete="RESTRICT"))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    license: Mapped[SourceLicense] = relationship()
    sla: Mapped[SourceSLA | None] = relationship(back_populates="source", uselist=False)

    __table_args__ = (
        sa.CheckConstraint("rate_limit_per_minute IS NULL OR rate_limit_per_minute > 0", name="positive_rate_limit"),
    )


class SourceSLA(Base):
    __tablename__ = "source_slas"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(sa.ForeignKey("data_sources.id", ondelete="CASCADE"), unique=True)
    expected_frequency_minutes: Mapped[int] = mapped_column()
    freshness_grace_minutes: Mapped[int] = mapped_column(default=0)
    last_success_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(sa.String(100))

    source: Mapped[DataSource] = relationship(back_populates="sla")

    __table_args__ = (
        sa.CheckConstraint("expected_frequency_minutes > 0", name="positive_frequency"),
        sa.CheckConstraint("freshness_grace_minutes >= 0", name="nonnegative_freshness_grace"),
    )


class SourceObject(Base):
    __tablename__ = "source_objects"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(sa.ForeignKey("data_sources.id", ondelete="RESTRICT"), index=True)
    logical_uri: Mapped[str] = mapped_column(sa.Text)
    object_type: Mapped[str] = mapped_column(sa.String(100))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    versions: Mapped[list[SourceObjectVersion]] = relationship(back_populates="source_object")

    __table_args__ = (sa.UniqueConstraint("source_id", "logical_uri", name="uq_source_objects_source_uri"),)


class SourceObjectVersion(Base):
    __tablename__ = "source_object_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_object_id: Mapped[UUID] = mapped_column(sa.ForeignKey("source_objects.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int]
    content_sha256: Mapped[str] = mapped_column(sa.String(64))
    storage_key: Mapped[str] = mapped_column(sa.Text, unique=True)
    etag: Mapped[str | None] = mapped_column(sa.Text)
    size_bytes: Mapped[int] = mapped_column()
    media_type: Mapped[str] = mapped_column(sa.String(200))
    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    parser_version: Mapped[str | None] = mapped_column(sa.String(100))
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)

    source_object: Mapped[SourceObject] = relationship(back_populates="versions")

    __table_args__ = (
        sa.UniqueConstraint("source_object_id", "version_number", name="uq_source_object_versions_number"),
        sa.UniqueConstraint("source_object_id", "content_sha256", name="uq_source_object_versions_hash"),
        sa.CheckConstraint("version_number > 0", name="positive_version"),
        sa.CheckConstraint("size_bytes >= 0", name="nonnegative_size"),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
    )


class IngestionAttempt(Base):
    __tablename__ = "ingestion_attempts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_object_id: Mapped[UUID] = mapped_column(sa.ForeignKey("source_objects.id", ondelete="CASCADE"), index=True)
    workflow_id: Mapped[str] = mapped_column(sa.String(255))
    attempt_number: Mapped[int]
    status: Mapped[str] = mapped_column(sa.String(20))
    error_code: Mapped[str | None] = mapped_column(sa.String(100))
    started_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    details: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        sa.UniqueConstraint("workflow_id", "attempt_number", name="uq_ingestion_attempts_workflow_attempt"),
        sa.CheckConstraint("attempt_number > 0", name="positive_attempt"),
        sa.CheckConstraint("status IN ('running', 'succeeded', 'failed', 'quarantined')", name="status_values"),
    )
