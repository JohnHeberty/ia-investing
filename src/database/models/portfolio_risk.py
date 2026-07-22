from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class InstitutionalRiskPolicy(Base):
    __tablename__ = "institutional_risk_policies"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    mandate_id: Mapped[UUID] = mapped_column(sa.ForeignKey("strategy_mandates.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column()
    methodology_version: Mapped[str] = mapped_column(sa.String(100))
    limits: Mapped[dict[str, object]] = mapped_column(JSONB)
    content_sha256: Mapped[str] = mapped_column(sa.String(64))
    status: Mapped[str] = mapped_column(sa.String(20), default="active")

    __table_args__ = (
        sa.UniqueConstraint("mandate_id", "version", name="uq_institutional_risk_policies_mandate_version"),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
    )


class InstitutionalRiskSnapshot(Base):
    __tablename__ = "institutional_risk_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("institutional_portfolio_versions.id", ondelete="CASCADE"), index=True
    )
    risk_policy_id: Mapped[UUID] = mapped_column(sa.ForeignKey("institutional_risk_policies.id", ondelete="RESTRICT"))
    as_of: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    input_sha256: Mapped[str] = mapped_column(sa.String(64))
    exposures: Mapped[dict[str, object]] = mapped_column(JSONB)
    concentration: Mapped[dict[str, object]] = mapped_column(JSONB)
    liquidity: Mapped[dict[str, object]] = mapped_column(JSONB)
    volatility: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 8))
    drawdown: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 8))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint(
            "portfolio_version_id", "risk_policy_id", "as_of", name="uq_risk_snapshots_version_policy_asof"
        ),
    )


class RiskBreach(Base):
    __tablename__ = "risk_breaches"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    risk_snapshot_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("institutional_risk_snapshots.id", ondelete="CASCADE"), index=True
    )
    limit_name: Mapped[str] = mapped_column(sa.String(150))
    limit_type: Mapped[str] = mapped_column(sa.String(10))
    observed_value: Mapped[Decimal] = mapped_column(sa.Numeric(20, 8))
    limit_value: Mapped[Decimal] = mapped_column(sa.Numeric(20, 8))
    status: Mapped[str] = mapped_column(sa.String(20), default="open")
    opened_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint("risk_snapshot_id", "limit_name", name="uq_risk_breaches_snapshot_limit"),
        sa.CheckConstraint("limit_type IN ('hard', 'soft')", name="limit_type_values"),
        sa.CheckConstraint("status IN ('open', 'waived', 'resolved')", name="status_values"),
    )


class RiskWaiver(Base):
    __tablename__ = "risk_waivers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    breach_id: Mapped[UUID] = mapped_column(sa.ForeignKey("risk_breaches.id", ondelete="CASCADE"), index=True)
    granted_by: Mapped[str] = mapped_column(sa.String(255))
    reason: Mapped[str] = mapped_column(sa.Text)
    granted_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (sa.CheckConstraint("expires_at > granted_at", name="valid_expiry"),)


class StressScenario(Base):
    __tablename__ = "stress_scenarios"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    logical_id: Mapped[str] = mapped_column(sa.String(100))
    version: Mapped[int] = mapped_column()
    shocks: Mapped[dict[str, object]] = mapped_column(JSONB)
    content_sha256: Mapped[str] = mapped_column(sa.String(64))

    __table_args__ = (
        sa.UniqueConstraint("logical_id", "version", name="uq_stress_scenarios_logical_version"),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
    )


class StressResult(Base):
    __tablename__ = "stress_results"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    risk_snapshot_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("institutional_risk_snapshots.id", ondelete="CASCADE"), index=True
    )
    scenario_id: Mapped[UUID] = mapped_column(sa.ForeignKey("stress_scenarios.id", ondelete="RESTRICT"))
    pnl_impact: Mapped[Decimal] = mapped_column(sa.Numeric(28, 8))
    nav_impact_ratio: Mapped[Decimal] = mapped_column(sa.Numeric(10, 8))
    result_payload: Mapped[dict[str, object]] = mapped_column(JSONB)

    __table_args__ = (
        sa.UniqueConstraint("risk_snapshot_id", "scenario_id", name="uq_stress_results_snapshot_scenario"),
    )
