from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("portfolios.id", ondelete="SET NULL"),
    )
    rebalance_proposal_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("rebalance_proposals.id", ondelete="SET NULL"),
    )

    approver_name: Mapped[str] = mapped_column(sa.String(200))
    decision: Mapped[str] = mapped_column(sa.String(20))
    notes_pt: Mapped[str] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"Approval(approver_name={self.approver_name!r}, decision={self.decision!r})"


class ExecutionReconciliation(Base):
    __tablename__ = "execution_reconciliations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    transaction_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("transactions.id", ondelete="SET NULL"),
    )

    broker_order_id: Mapped[str] = mapped_column(sa.String(100))
    status: Mapped[str] = mapped_column(sa.String(20))
    discrepancy_notes: Mapped[str] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"ExecutionReconciliation(status={self.status!r}, broker_order_id={self.broker_order_id!r})"


class EvaluationResultRecord(Base):
    """Avaliações de qualidade dos agentes."""

    __tablename__ = "evaluation_results"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    agent_definition_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("agent_definitions.id", ondelete="SET NULL"),
    )

    evaluation_type: Mapped[str] = mapped_column(sa.String(50))
    metric_name: Mapped[str] = mapped_column(sa.String(100))
    value: Mapped[float] = mapped_column(sa.Float)

    dataset_id: Mapped[UUID] = mapped_column()
    model_version: Mapped[str] = mapped_column(sa.String(100))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return (
            f"EvaluationResultRecord(evaluation_type={self.evaluation_type!r}, "
            f"metric_name={self.metric_name!r}, value={self.value})"
        )


class AuditLog(Base):
    """Auditoria imutável de ações do sistema."""

    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    actor_id: Mapped[str] = mapped_column(sa.String(255), nullable=False)

    action: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(nullable=False, index=True)

    details: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=utcnow)

    def __repr__(self) -> str:
        return f"AuditLog(actor_type={self.actor_type!r}, action={self.action!r})"
