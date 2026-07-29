from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class StrategyMandate(Base):
    __tablename__ = "strategy_mandates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(sa.ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    logical_id: Mapped[str] = mapped_column(sa.String(100))
    version: Mapped[int] = mapped_column()
    benchmark_index_id: Mapped[UUID] = mapped_column(sa.ForeignKey("market_indices.id", ondelete="RESTRICT"))
    base_currency: Mapped[str] = mapped_column(sa.String(3), default="BRL")
    config: Mapped[dict[str, object]] = mapped_column(JSONB)
    content_sha256: Mapped[str] = mapped_column(sa.String(64))
    status: Mapped[str] = mapped_column(sa.String(20), default="draft")
    created_by: Mapped[str] = mapped_column(sa.String(255))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint(
            "organization_id", "logical_id", "version", name="uq_strategy_mandates_org_logical_version"
        ),
        sa.CheckConstraint("version > 0", name="positive_version"),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        sa.CheckConstraint("base_currency ~ '^[A-Z]{3}$'", name="currency_format"),
        sa.CheckConstraint("status IN ('draft', 'active', 'retired')", name="status_values"),
    )


class ModelPortfolio(Base):
    __tablename__ = "model_portfolios"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(sa.ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    owner_team_id: Mapped[UUID] = mapped_column(sa.ForeignKey("teams.id", ondelete="RESTRICT"))
    mandate_id: Mapped[UUID] = mapped_column(sa.ForeignKey("strategy_mandates.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(sa.String(200))
    base_currency: Mapped[str] = mapped_column(sa.String(3))
    state: Mapped[str] = mapped_column(sa.String(30), default="draft")
    environment: Mapped[str] = mapped_column(sa.String(10), default="paper")
    lock_version: Mapped[int] = mapped_column(default=1)
    created_by: Mapped[str] = mapped_column(sa.String(255))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (
        sa.UniqueConstraint("organization_id", "name", name="uq_model_portfolios_organization_name"),
        sa.CheckConstraint(
            "state IN ('draft', 'researching', 'simulated', 'committee_review', 'approved', 'paper_live', "
            "'eligible_for_live', 'live', 'suspended', 'archived')",
            name="state_values",
        ),
        sa.CheckConstraint("environment IN ('paper', 'live')", name="environment_values"),
    )
