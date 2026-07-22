from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

AUDIT_ACTIONS = frozenset(
    {
        "create",
        "update",
        "delete",
        "read",
        "execute",
        "approve",
        "reject",
        "login",
        "logout",
        "export",
        "config_change",
    }
)


class AuditLogEntry(Base):
    __tablename__ = "audit_log_entries"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=sa.func.gen_random_uuid())
    tenant_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    resource_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    changes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    meta_data: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    hash_prev: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    hash: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True)
    timestamp: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        sa.Index("ix_audit_log_tenant_timestamp", "tenant_id", "timestamp"),
        sa.Index("ix_audit_log_actor", "actor_id"),
        sa.Index("ix_audit_log_resource", "resource_type", "resource_id"),
        sa.CheckConstraint(
            "action IN ('create','update','delete','read','execute','approve',"
            "'reject','login','logout','export','config_change')",
            name="ck_audit_log_action",
        ),
    )

    def compute_hash(self) -> str:
        raw = (
            str(self.hash_prev or "")
            + self.timestamp.isoformat()
            + str(self.actor_id or "")
            + self.action
            + self.resource_type
            + str(self.resource_id or "")
            + json.dumps(self.changes or {}, sort_keys=True)
            + json.dumps(self.meta_data or {}, sort_keys=True)
        )
        return sha256(raw.encode("utf-8")).hexdigest()

    def __repr__(self) -> str:
        return f"AuditLogEntry(action={self.action!r}, resource_type={self.resource_type!r})"
