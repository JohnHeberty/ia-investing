from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class Operation(Base):
    """Tenant-scoped durable command record.

    Temporal is the execution engine; this table is the authorization-safe,
    queryable control-plane record exposed by the API.
    """

    __tablename__ = "operations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
        index=True,
    )
    operation_type: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="pending")
    request_data: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    result_data: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    result_url: Mapped[str | None] = mapped_column(sa.Text)
    error_code: Mapped[str | None] = mapped_column(sa.String(100))
    error_detail: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "organization_id",
            "operation_type",
            "idempotency_key",
            name="uq_operations_org_type_idempotency_key",
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
            name="operation_state",
        ),
        sa.CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="operation_request_hash_format"),
    )


class OperationDispatchOutbox(Base):
    """Transactional hand-off from PostgreSQL commands to Temporal."""

    __tablename__ = "operation_dispatch_outbox"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    operation_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("operations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    topic: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(sa.String(200))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    __table_args__ = (
        sa.CheckConstraint(
            "state IN ('pending', 'dispatched', 'failed')",
            name="operation_dispatch_outbox_state",
        ),
        sa.CheckConstraint("attempts >= 0", name="operation_dispatch_outbox_attempts_nonnegative"),
        sa.Index(
            "ix_operation_dispatch_outbox_pending",
            "state",
            "next_attempt_at",
            postgresql_where=sa.text("state = 'pending'"),
        ),
    )
