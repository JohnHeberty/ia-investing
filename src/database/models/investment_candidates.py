from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class InvestmentCandidateRecord(Base):
    __tablename__ = "investment_candidates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    origin: Mapped[str] = mapped_column(sa.String(20), index=True)
    status: Mapped[str] = mapped_column(sa.String(40), index=True)
    ticker: Mapped[str] = mapped_column(sa.String(24), index=True)
    exchange: Mapped[str] = mapped_column(sa.String(20), default="B3")
    legal_name: Mapped[str | None] = mapped_column(sa.String(300))
    trading_name: Mapped[str | None] = mapped_column(sa.String(300))
    cnpj: Mapped[str | None] = mapped_column(sa.String(32), index=True)
    cvm_code: Mapped[str | None] = mapped_column(sa.String(32), index=True)
    issuer_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("issuers.id", ondelete="RESTRICT"),
        index=True,
    )
    instrument_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("instruments.id", ondelete="RESTRICT"),
        index=True,
    )
    rationale: Mapped[str | None] = mapped_column(sa.Text)
    exploration_suggestion_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey(
            "exploration_suggestions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_investment_candidates_exploration_suggestion",
        ),
        index=True,
    )
    final_decision: Mapped[str | None] = mapped_column(sa.String(20), index=True)
    final_decision_reason: Mapped[str | None] = mapped_column(sa.Text)
    approved_portfolio_eligible: Mapped[bool] = mapped_column(default=False, index=True)
    created_by: Mapped[str] = mapped_column(sa.String(255))
    idempotency_key: Mapped[str] = mapped_column(sa.String(255))
    request_hash: Mapped[str] = mapped_column(sa.String(64))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=utcnow,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )
    lock_version: Mapped[int] = mapped_column(default=1)

    __table_args__ = (
        sa.CheckConstraint("origin IN ('manual', 'explorer')", name="candidate_origin_values"),
        sa.CheckConstraint(
            "status IN ('suggested','identity_resolution','source_discovery',"
            "'awaiting_user_input','source_validation','document_collection',"
            "'data_quality','fundamental_analysis','risk_analysis','committee_review',"
            "'approved','rejected','watchlist','cancelled')",
            name="candidate_status_values",
        ),
        sa.CheckConstraint(
            "final_decision IS NULL OR final_decision IN ('approve','reject','pending','watchlist')",
            name="candidate_final_decision_values",
        ),
        sa.CheckConstraint("lock_version > 0", name="candidate_positive_lock_version"),
        sa.CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="candidate_request_hash_format"),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_candidate_org_idempotency"),
        sa.Index(
            "ix_candidate_org_status_updated",
            "organization_id",
            "status",
            sa.desc("updated_at"),
        ),
        sa.Index(
            "uq_candidate_active_ticker",
            "organization_id",
            "exchange",
            "ticker",
            unique=True,
            postgresql_where=sa.text("status <> 'cancelled'"),
        ),
    )


class CandidateSourceRecord(Base):
    __tablename__ = "candidate_sources"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("investment_candidates.id", ondelete="CASCADE"),
        index=True,
    )
    kind: Mapped[str] = mapped_column(sa.String(40), index=True)
    url: Mapped[str] = mapped_column(sa.Text)
    normalized_url_hash: Mapped[str] = mapped_column(sa.String(64))
    status: Mapped[str] = mapped_column(sa.String(20), index=True)
    verification_method: Mapped[str] = mapped_column(sa.String(40))
    confidence: Mapped[Decimal] = mapped_column(sa.Numeric(5, 4))
    official: Mapped[bool] = mapped_column(default=False)
    discovered_by: Mapped[str] = mapped_column(sa.String(255))
    notes: Mapped[str | None] = mapped_column(sa.Text)
    evidence: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    verified_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    last_checked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), index=True)

    __table_args__ = (
        sa.UniqueConstraint(
            "candidate_id",
            "kind",
            "normalized_url_hash",
            name="uq_candidate_source_kind_url",
        ),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="candidate_source_confidence_range"),
        sa.CheckConstraint(
            "status IN ('discovered','verified','rejected','stale','unreachable')",
            name="candidate_source_status_values",
        ),
        sa.CheckConstraint(
            "NOT (official AND verification_method = 'agent_inference')",
            name="candidate_source_agent_cannot_confirm_official",
        ),
        sa.CheckConstraint(
            "status <> 'verified' OR verified_at IS NOT NULL",
            name="candidate_source_verified_timestamp",
        ),
    )


class CandidateGapRecord(Base):
    __tablename__ = "candidate_gaps"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("investment_candidates.id", ondelete="CASCADE"),
        index=True,
    )
    code: Mapped[str] = mapped_column(sa.String(100), index=True)
    title: Mapped[str] = mapped_column(sa.String(500))
    description: Mapped[str] = mapped_column(sa.Text)
    source_kind: Mapped[str | None] = mapped_column(sa.String(40))
    level: Mapped[str] = mapped_column(sa.String(20), index=True)
    status: Mapped[str] = mapped_column(sa.String(20), default="open", index=True)
    requested_user_action: Mapped[str] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(sa.String(255))
    resolution_notes: Mapped[str | None] = mapped_column(sa.Text)

    __table_args__ = (
        sa.CheckConstraint("level IN ('blocking','required','optional')", name="candidate_gap_level_values"),
        sa.CheckConstraint("status IN ('open','resolved','waived')", name="candidate_gap_status_values"),
        sa.CheckConstraint(
            "status = 'open' OR (resolved_at IS NOT NULL AND resolved_by IS NOT NULL)",
            name="candidate_gap_resolution_fields",
        ),
        sa.Index(
            "uq_candidate_open_gap_code",
            "candidate_id",
            "code",
            unique=True,
            postgresql_where=sa.text("status = 'open'"),
        ),
    )


class CandidateAnalysisRunRecord(Base):
    __tablename__ = "candidate_analysis_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("investment_candidates.id", ondelete="CASCADE"),
        index=True,
    )
    run_number: Mapped[int]
    trigger: Mapped[str] = mapped_column(sa.String(30))
    status: Mapped[str] = mapped_column(sa.String(20), index=True)
    requested_by: Mapped[str] = mapped_column(sa.String(255))
    requested_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    data_as_of: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)
    workflow_id: Mapped[str | None] = mapped_column(sa.String(255), unique=True)
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    decision: Mapped[str | None] = mapped_column(sa.String(20))
    summary: Mapped[str | None] = mapped_column(sa.Text)
    blocker_codes: Mapped[list[str]] = mapped_column(JSONB, default=list)
    agent_run_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    research_case_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("research_cases.id", ondelete="SET NULL"),
        index=True,
    )
    thesis_version_id: Mapped[UUID | None] = mapped_column(index=True)
    committee_decision_id: Mapped[UUID | None] = mapped_column(index=True)
    error_code: Mapped[str | None] = mapped_column(sa.String(100))
    error_detail: Mapped[str | None] = mapped_column(sa.Text)

    __table_args__ = (
        sa.UniqueConstraint("candidate_id", "run_number", name="uq_candidate_analysis_run_number"),
        sa.CheckConstraint("run_number > 0", name="candidate_run_positive_number"),
        sa.CheckConstraint(
            "status IN ('queued','running','blocked','succeeded','failed','cancelled')",
            name="candidate_run_status_values",
        ),
        sa.CheckConstraint(
            "decision IS NULL OR decision IN ('approve','reject','pending','watchlist')",
            name="candidate_run_decision_values",
        ),
    )


class ExplorationRunRecord(Base):
    __tablename__ = "exploration_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    status: Mapped[str] = mapped_column(sa.String(20), index=True)
    strategy_codes: Mapped[list[str]] = mapped_column(JSONB)
    requested_by: Mapped[str] = mapped_column(sa.String(255))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow, index=True)
    data_as_of: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)
    minimum_liquidity: Mapped[Decimal] = mapped_column(sa.Numeric(24, 6))
    maximum_suggestions: Mapped[int]
    excluded_instrument_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    workflow_id: Mapped[str | None] = mapped_column(sa.String(255), unique=True)
    universe_size: Mapped[int] = mapped_column(default=0)
    eligible_size: Mapped[int] = mapped_column(default=0)
    error_detail: Mapped[str | None] = mapped_column(sa.Text)

    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','partial','failed','cancelled')",
            name="exploration_run_status_values",
        ),
        sa.CheckConstraint("minimum_liquidity >= 0", name="exploration_nonnegative_liquidity"),
        sa.CheckConstraint(
            "maximum_suggestions BETWEEN 1 AND 100",
            name="exploration_suggestion_limit",
        ),
    )


class ExplorationSuggestionRecord(Base):
    __tablename__ = "exploration_suggestions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    exploration_run_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("exploration_runs.id", ondelete="CASCADE"),
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    instrument_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("instruments.id", ondelete="RESTRICT"),
        index=True,
    )
    issuer_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("issuers.id", ondelete="RESTRICT"),
        index=True,
    )
    ticker: Mapped[str] = mapped_column(sa.String(24), index=True)
    exchange: Mapped[str] = mapped_column(sa.String(20))
    status: Mapped[str] = mapped_column(sa.String(20), index=True)
    quantitative_score: Mapped[Decimal] = mapped_column(sa.Numeric(5, 4))
    data_coverage_score: Mapped[Decimal] = mapped_column(sa.Numeric(5, 4))
    source_discovery_score: Mapped[Decimal] = mapped_column(sa.Numeric(5, 4))
    rationale: Mapped[str] = mapped_column(sa.Text)
    signals: Mapped[list[str]] = mapped_column(JSONB, default=list)
    risks: Mapped[list[str]] = mapped_column(JSONB, default=list)
    source_snapshot: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), index=True)
    promoted_candidate_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey(
            "investment_candidates.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_exploration_suggestions_promoted_candidate",
        ),
        index=True,
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    dismissed_by: Mapped[str | None] = mapped_column(sa.String(255))
    dismissal_reason: Mapped[str | None] = mapped_column(sa.Text)

    __table_args__ = (
        sa.UniqueConstraint(
            "exploration_run_id",
            "instrument_id",
            name="uq_exploration_suggestion_instrument",
        ),
        sa.CheckConstraint(
            "status IN ('new','promoted','dismissed','duplicate','expired')",
            name="exploration_suggestion_status_values",
        ),
        sa.CheckConstraint(
            "quantitative_score BETWEEN 0 AND 1 AND "
            "data_coverage_score BETWEEN 0 AND 1 AND "
            "source_discovery_score BETWEEN 0 AND 1",
            name="exploration_suggestion_score_ranges",
        ),
        sa.CheckConstraint(
            "status <> 'dismissed' OR "
            "(dismissed_at IS NOT NULL AND dismissed_by IS NOT NULL AND dismissal_reason IS NOT NULL)",
            name="exploration_suggestion_dismissal_fields",
        ),
    )


class CandidateEventRecord(Base):
    __tablename__ = "candidate_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("investment_candidates.id", ondelete="CASCADE"),
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    event_type: Mapped[str] = mapped_column(sa.String(100), index=True)
    actor_type: Mapped[str] = mapped_column(sa.String(30))
    actor_id: Mapped[str] = mapped_column(sa.String(255))
    occurred_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow, index=True)
    aggregate_version: Mapped[int]
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        sa.CheckConstraint("aggregate_version > 0", name="candidate_event_positive_version"),
        sa.Index(
            "ix_candidate_event_timeline",
            "candidate_id",
            sa.desc("occurred_at"),
        ),
    )


# --- Append-only audit protection -------------------------------------------

def _reject_event_update(mapper: Any, connection: Any, target: CandidateEventRecord) -> None:
    raise sa.exc.StatementError(
        "UPDATE is not allowed on candidate_events (append-only audit log)",
        "",
        {},
        None,
    )


def _reject_event_delete(mapper: Any, connection: Any, target: CandidateEventRecord) -> None:
    raise sa.exc.StatementError(
        "DELETE is not allowed on candidate_events (append-only audit log)",
        "",
        {},
        None,
    )


event.listen(CandidateEventRecord, "before_update", _reject_event_update)
event.listen(CandidateEventRecord, "before_delete", _reject_event_delete)
