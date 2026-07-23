from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[str] = mapped_column(sa.String(100), nullable=False, index=True)
    portfolio_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("portfolios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(20, 4), nullable=False)
    price_limit: Mapped[Decimal | None] = mapped_column(sa.Numeric(14, 6))
    state: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="pending")
    available_balance: Mapped[Decimal] = mapped_column(sa.Numeric(20, 4), nullable=False, default=0)
    required_amount: Mapped[Decimal] = mapped_column(sa.Numeric(20, 4), nullable=False, default=0)
    alert_triggered: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    filled_quantity: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 4))
    avg_price: Mapped[Decimal | None] = mapped_column(sa.Numeric(14, 6))
    reason: Mapped[str | None] = mapped_column(sa.Text)
    dispatched_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    settled_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
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
