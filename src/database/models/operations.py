from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


class Operation(Base):
    __tablename__ = "operations"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
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
        sa.UniqueConstraint("operation_type", "idempotency_key", name="uq_operations_type_idempotency_key"),
        sa.CheckConstraint(
            "state IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
            name="operation_state",
        ),
    )
