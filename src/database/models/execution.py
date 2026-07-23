import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from ._utils import utcnow
from .base import Base


class Execution(Base):
    __tablename__ = "executions"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    order_id = sa.Column(sa.String(100), nullable=False, index=True)
    portfolio_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("portfolios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    action = sa.Column(sa.String(10), nullable=False)
    quantity = sa.Column(sa.Numeric(20, 4), nullable=False)
    price_limit = sa.Column(sa.Numeric(14, 6))
    state = sa.Column(sa.String(20), nullable=False, default="pending")
    available_balance = sa.Column(sa.Numeric(20, 4), nullable=False, default=0)
    required_amount = sa.Column(sa.Numeric(20, 4), nullable=False, default=0)
    alert_triggered = sa.Column(sa.Boolean, nullable=False, default=False)
    filled_quantity = sa.Column(sa.Numeric(20, 4))
    avg_price = sa.Column(sa.Numeric(14, 6))
    reason = sa.Column(sa.Text)
    dispatched_at = sa.Column(sa.DateTime(timezone=True))
    confirmed_at = sa.Column(sa.DateTime(timezone=True))
    settled_at = sa.Column(sa.DateTime(timezone=True))
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    __table_args__ = (
        sa.CheckConstraint(
            "action IN ('buy','sell')",
            name="ck_execution_action",
        ),
        sa.CheckConstraint(
            "state IN ('pending','validated','queued','dispatched','confirmed','failed','settled')",
            name="ck_execution_state",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_execution_quantity_positive"),
        sa.CheckConstraint("available_balance >= 0", name="ck_execution_available_balance_nonnegative"),
        sa.CheckConstraint("required_amount >= 0", name="ck_execution_required_amount_nonnegative"),
        sa.Index("ix_executions_portfolio_state", "portfolio_id", "state"),
        sa.Index("ix_executions_state_created", "state", "created_at"),
    )
