from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


class Operation(Base):
    """Tenant-scoped durable command record.

    Temporal is the execution engine; this table is the authorization-safe,
    queryable control-plane record exposed by the API.
    """

    __tablename__ = "operations"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    organization_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    operation_type = sa.Column(sa.String(100), nullable=False)
    idempotency_key = sa.Column(sa.String(200), nullable=False)
    request_hash = sa.Column(sa.String(64), nullable=False)
    state = sa.Column(sa.String(20), nullable=False, default="pending")
    request_data = sa.Column(JSONB, nullable=False)
    result_data = sa.Column(JSONB)
    result_url = sa.Column(sa.Text)
    error_code = sa.Column(sa.String(100))
    error_detail = sa.Column(sa.Text)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
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

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    organization_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    operation_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("operations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    topic = sa.Column(sa.String(100), nullable=False)
    state = sa.Column(sa.String(20), nullable=False, default="pending")
    attempts = sa.Column(sa.Integer, nullable=False, default=0)
    next_attempt_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    dispatched_at = sa.Column(sa.DateTime(timezone=True))
    last_error = sa.Column(sa.String(200))
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
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
