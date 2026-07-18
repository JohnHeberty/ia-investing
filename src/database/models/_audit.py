from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


class Approval(Base):
    __tablename__ = "approvals"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    portfolio_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("portfolios.id", ondelete="SET NULL"),
    )
    rebalance_proposal_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("rebalance_proposals.id", ondelete="SET NULL"),
    )

    approver_name = sa.Column(sa.String(200))
    decision = sa.Column(sa.String(20))  # "approved", "rejected"
    notes_pt = sa.Column(sa.Text)

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"Approval(approver_name={self.approver_name!r}, decision={self.decision!r})"


class ExecutionReconciliation(Base):
    __tablename__ = "execution_reconciliations"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    transaction_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("transactions.id", ondelete="SET NULL"),
    )

    broker_order_id = sa.Column(sa.String(100))
    status = sa.Column(sa.String(20))  # "matched", "unmatched"
    discrepancy_notes = sa.Column(sa.Text)

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"ExecutionReconciliation(status={self.status!r}, broker_order_id={self.broker_order_id!r})"


class EvaluationResult(Base):
    """Avaliações de qualidade dos agentes."""

    __tablename__ = "evaluation_results"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    agent_definition_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("agent_definitions.id", ondelete="SET NULL"),
    )

    evaluation_type = sa.Column(sa.String(50))  # "extraction", "interpretation", "decision"
    metric_name = sa.Column(sa.String(100))
    value = sa.Column(sa.Float)

    dataset_id = sa.Column(UUID(as_uuid=True))
    model_version = sa.Column(sa.String(100))

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return (
            f"EvaluationResult(evaluation_type={self.evaluation_type!r}, "
            f"metric_name={self.metric_name!r}, value={self.value})"
        )


class AuditLog(Base):
    """Auditoria imutável de ações do sistema."""

    __tablename__ = "audit_logs"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    actor_type = sa.Column(sa.String(50))  # "agent", "human", "system"
    actor_id = sa.Column(UUID(as_uuid=True))

    action = sa.Column(sa.String(100))
    entity_type = sa.Column(sa.String(50))
    entity_id = sa.Column(UUID(as_uuid=True))

    details = JSONB()
    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"AuditLog(actor_type={self.actor_type!r}, action={self.action!r})"
