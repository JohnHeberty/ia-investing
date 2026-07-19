from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class QualityRule(Base):
    __tablename__ = "quality_rules"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(sa.String(100))
    version: Mapped[int]
    severity: Mapped[str] = mapped_column(sa.String(20))
    is_material: Mapped[bool]
    tolerance: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    valid_from: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint("code", "version", name="uq_quality_rules_code_version"),
        sa.CheckConstraint("version > 0", name="positive_version"),
        sa.CheckConstraint("severity IN ('critical', 'error', 'warning', 'info')", name="severity_values"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="valid_window"),
    )


class QualityIncident(Base):
    __tablename__ = "quality_incidents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    quality_rule_id: Mapped[UUID] = mapped_column(sa.ForeignKey("quality_rules.id", ondelete="RESTRICT"), index=True)
    source_object_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("source_object_versions.id", ondelete="RESTRICT"), index=True
    )
    financial_fact_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("financial_facts.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(sa.String(20), default="open")
    severity: Mapped[str] = mapped_column(sa.String(20))
    owner_role: Mapped[str] = mapped_column(sa.String(100))
    impact_summary: Mapped[str] = mapped_column(sa.Text)
    evidence: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    resolution_notes: Mapped[str | None] = mapped_column(sa.Text)
    waiver_reason: Mapped[str | None] = mapped_column(sa.Text)
    waiver_approved_by: Mapped[str | None] = mapped_column(sa.String(255))
    waiver_expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (
        sa.UniqueConstraint(
            "quality_rule_id",
            "source_object_version_id",
            name="uq_quality_incidents_rule_source_version",
        ),
        sa.CheckConstraint("status IN ('open', 'acknowledged', 'resolved', 'waived')", name="status_values"),
        sa.CheckConstraint("severity IN ('critical', 'error', 'warning', 'info')", name="severity_values"),
        sa.CheckConstraint(
            "status <> 'waived' OR (waiver_reason IS NOT NULL AND waiver_approved_by IS NOT NULL "
            "AND waiver_expires_at IS NOT NULL)",
            name="waiver_fields_required",
        ),
    )


class QuarantineRecord(Base):
    __tablename__ = "quarantine_records"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_object_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("source_object_versions.id", ondelete="RESTRICT"), index=True
    )
    quality_incident_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("quality_incidents.id", ondelete="CASCADE"), unique=True
    )
    stage: Mapped[str] = mapped_column(sa.String(50))
    payload_reference: Mapped[str] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.String(20), default="blocked")
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    released_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (sa.CheckConstraint("status IN ('blocked', 'released', 'discarded')", name="status_values"),)
