from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class ExecutionModelVersion(Base):
    __tablename__ = "execution_model_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    logical_id: Mapped[str] = mapped_column(sa.String(100))
    version: Mapped[int]
    configuration: Mapped[dict[str, object]] = mapped_column(JSONB)
    content_sha256: Mapped[str] = mapped_column(sa.String(64))
    status: Mapped[str] = mapped_column(sa.String(20), default="draft")
    created_by: Mapped[str] = mapped_column(sa.String(200))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint("organization_id", "logical_id", "version", name="uq_execution_models_org_logical_version"),
        sa.CheckConstraint("version > 0", name="positive_version"),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        sa.CheckConstraint("status IN ('draft', 'approved', 'retired')", name="status_values"),
    )


class TradeIntent(Base):
    __tablename__ = "paper_trade_intents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    portfolio_id: Mapped[UUID] = mapped_column(sa.ForeignKey("model_portfolios.id", ondelete="CASCADE"), index=True)
    portfolio_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("institutional_portfolio_versions.id", ondelete="RESTRICT"), index=True
    )
    instrument_id: Mapped[UUID] = mapped_column(sa.ForeignKey("instruments.id", ondelete="RESTRICT"))
    idempotency_key: Mapped[str] = mapped_column(sa.String(200))
    side: Mapped[str] = mapped_column(sa.String(4))
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(28, 10))
    order_type: Mapped[str] = mapped_column(sa.String(20), default="market")
    limit_price: Mapped[Decimal | None] = mapped_column(sa.Numeric(28, 10))
    earliest_execution_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(sa.Text)
    approval_decision: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(sa.String(30), default="draft")
    environment: Mapped[str] = mapped_column(sa.String(10), default="paper")
    created_by: Mapped[str] = mapped_column(sa.String(200))
    approved_by: Mapped[str | None] = mapped_column(sa.String(200))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_trade_intents_org_idempotency"),
        sa.CheckConstraint("side IN ('buy', 'sell')", name="side_values"),
        sa.CheckConstraint("quantity > 0", name="positive_quantity"),
        sa.CheckConstraint("order_type IN ('market', 'limit')", name="order_type_values"),
        sa.CheckConstraint("(order_type = 'limit') = (limit_price IS NOT NULL)", name="limit_price_required"),
        sa.CheckConstraint("limit_price IS NULL OR limit_price > 0", name="positive_limit_price"),
        sa.CheckConstraint("expires_at > earliest_execution_at", name="valid_execution_window"),
        sa.CheckConstraint(
            "status IN ('draft', 'pending_approval', 'approved', 'submitted', "
            "'completed', 'cancelled', 'expired', 'failed')",
            name="status_values",
        ),
        sa.CheckConstraint("environment = 'paper'", name="paper_only"),
    )


class PaperOrder(Base):
    __tablename__ = "paper_orders"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    trade_intent_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("paper_trade_intents.id", ondelete="RESTRICT"), index=True
    )
    execution_model_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("execution_model_versions.id", ondelete="RESTRICT")
    )
    submit_key: Mapped[str] = mapped_column(sa.String(200), unique=True)
    status: Mapped[str] = mapped_column(sa.String(30), default="created")
    requested_quantity: Mapped[Decimal] = mapped_column(sa.Numeric(28, 10))
    filled_quantity: Mapped[Decimal] = mapped_column(sa.Numeric(28, 10), default=0)
    input_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB)
    input_sha256: Mapped[str] = mapped_column(sa.String(64))
    seed: Mapped[int]
    environment: Mapped[str] = mapped_column(sa.String(10), default="paper")
    accepted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('created', 'accepted', 'partially_filled', 'filled', 'cancelled', 'rejected', 'expired')",
            name="status_values",
        ),
        sa.CheckConstraint("requested_quantity > 0", name="positive_requested_quantity"),
        sa.CheckConstraint(
            "filled_quantity >= 0 AND filled_quantity <= requested_quantity", name="valid_filled_quantity"
        ),
        sa.CheckConstraint("input_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        sa.CheckConstraint("environment = 'paper'", name="paper_only"),
    )


class PaperFill(Base):
    __tablename__ = "paper_fills"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(sa.ForeignKey("paper_orders.id", ondelete="RESTRICT"), index=True)
    event_key: Mapped[str] = mapped_column(sa.String(200), unique=True)
    sequence: Mapped[int]
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(28, 10))
    price: Mapped[Decimal] = mapped_column(sa.Numeric(28, 10))
    gross_value: Mapped[Decimal] = mapped_column(sa.Numeric(28, 10))
    fee_value: Mapped[Decimal] = mapped_column(sa.Numeric(28, 10))
    tax_value: Mapped[Decimal] = mapped_column(sa.Numeric(28, 10))
    slippage_bps: Mapped[Decimal] = mapped_column(sa.Numeric(12, 6))
    market_timestamp: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    filled_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    environment: Mapped[str] = mapped_column(sa.String(10), default="paper")

    __table_args__ = (
        sa.UniqueConstraint("order_id", "sequence", name="uq_paper_fills_order_sequence"),
        sa.CheckConstraint("sequence > 0", name="positive_sequence"),
        sa.CheckConstraint("quantity > 0 AND price > 0", name="positive_fill"),
        sa.CheckConstraint("gross_value = quantity * price", name="gross_value_identity"),
        sa.CheckConstraint("fee_value >= 0 AND tax_value >= 0", name="nonnegative_costs"),
        sa.CheckConstraint("environment = 'paper'", name="paper_only"),
    )


class ReconciliationBreak(Base):
    __tablename__ = "paper_reconciliation_breaks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    portfolio_id: Mapped[UUID] = mapped_column(sa.ForeignKey("model_portfolios.id", ondelete="CASCADE"), index=True)
    as_of: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    rule: Mapped[str] = mapped_column(sa.String(100))
    resource_key: Mapped[str] = mapped_column(sa.String(200))
    expected: Mapped[dict[str, object]] = mapped_column(JSONB)
    actual: Mapped[dict[str, object]] = mapped_column(JSONB)
    severity: Mapped[str] = mapped_column(sa.String(20))
    owner_role: Mapped[str] = mapped_column(sa.String(100), default="operations")
    status: Mapped[str] = mapped_column(sa.String(20), default="open")
    blocking: Mapped[bool] = mapped_column(default=False)
    resolution: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    detected_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint("portfolio_id", "as_of", "rule", "resource_key", name="uq_reconciliation_break_identity"),
        sa.CheckConstraint("severity IN ('info', 'warning', 'critical')", name="severity_values"),
        sa.CheckConstraint("status IN ('open', 'acknowledged', 'resolved', 'waived')", name="status_values"),
        sa.CheckConstraint("NOT blocking OR severity = 'critical'", name="only_critical_blocks"),
    )


class OperationalAlert(Base):
    __tablename__ = "operational_alerts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    portfolio_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("model_portfolios.id", ondelete="CASCADE"))
    deduplication_key: Mapped[str] = mapped_column(sa.String(250))
    alert_type: Mapped[str] = mapped_column(sa.String(80))
    severity: Mapped[str] = mapped_column(sa.String(20))
    rule_version: Mapped[str] = mapped_column(sa.String(50), default="v1")
    route: Mapped[str] = mapped_column(sa.String(100), default="operations")
    status: Mapped[str] = mapped_column(sa.String(20), default="open")
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    acknowledged_by: Mapped[str | None] = mapped_column(sa.String(200))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint("organization_id", "deduplication_key", name="uq_operational_alerts_org_dedup"),
        sa.CheckConstraint("severity IN ('info', 'warning', 'critical')", name="severity_values"),
        sa.CheckConstraint("status IN ('open', 'acknowledged', 'resolved')", name="status_values"),
    )


class PaperKillSwitch(Base):
    __tablename__ = "paper_kill_switches"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    portfolio_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("model_portfolios.id", ondelete="CASCADE"))
    active: Mapped[bool] = mapped_column(default=True)
    reason: Mapped[str] = mapped_column(sa.Text)
    activated_by: Mapped[str] = mapped_column(sa.String(200))
    activated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    released_by: Mapped[str | None] = mapped_column(sa.String(200))
    released_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.CheckConstraint(
            "active OR (released_by IS NOT NULL AND released_at IS NOT NULL)", name="release_is_attributed"
        ),
    )


class PaperPostMortem(Base):
    __tablename__ = "paper_post_mortems"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    portfolio_id: Mapped[UUID] = mapped_column(sa.ForeignKey("model_portfolios.id", ondelete="CASCADE"), index=True)
    version: Mapped[int]
    period_start: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    expected: Mapped[dict[str, object]] = mapped_column(JSONB)
    realized: Mapped[dict[str, object]] = mapped_column(JSONB)
    attribution: Mapped[dict[str, object]] = mapped_column(JSONB)
    findings: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    dissent: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    content_sha256: Mapped[str] = mapped_column(sa.String(64))
    created_by: Mapped[str] = mapped_column(sa.String(200))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint("portfolio_id", "version", name="uq_paper_post_mortems_portfolio_version"),
        sa.CheckConstraint("version > 0", name="positive_version"),
        sa.CheckConstraint("period_end > period_start", name="valid_period"),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
    )


class ChallengerEvaluation(Base):
    __tablename__ = "challenger_evaluations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    mandate_id: Mapped[UUID] = mapped_column(sa.ForeignKey("strategy_mandates.id", ondelete="CASCADE"), index=True)
    champion_portfolio_id: Mapped[UUID] = mapped_column(sa.ForeignKey("model_portfolios.id", ondelete="RESTRICT"))
    challenger_portfolio_id: Mapped[UUID] = mapped_column(sa.ForeignKey("model_portfolios.id", ondelete="RESTRICT"))
    window_start: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    methodology_version: Mapped[str] = mapped_column(sa.String(100))
    comparison_sha256: Mapped[str] = mapped_column(sa.String(64))
    comparison_config: Mapped[dict[str, object]] = mapped_column(JSONB)
    metrics: Mapped[dict[str, object]] = mapped_column(JSONB)
    evidence: Mapped[dict[str, object]] = mapped_column(JSONB)
    decision: Mapped[str] = mapped_column(sa.String(30), default="pending_committee")
    created_by: Mapped[str] = mapped_column(sa.String(200))
    decided_by: Mapped[str | None] = mapped_column(sa.String(200))
    decided_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint(
            "mandate_id",
            "challenger_portfolio_id",
            "window_start",
            "window_end",
            name="uq_challenger_evaluation_window",
        ),
        sa.CheckConstraint("champion_portfolio_id <> challenger_portfolio_id", name="different_portfolios"),
        sa.CheckConstraint("window_end > window_start", name="valid_window"),
        sa.CheckConstraint("comparison_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        sa.CheckConstraint(
            "decision IN ('pending_committee', 'retained', 'promoted', 'rejected')", name="decision_values"
        ),
        sa.CheckConstraint("decision = 'pending_committee' OR decided_by IS NOT NULL", name="decision_requires_human"),
    )
