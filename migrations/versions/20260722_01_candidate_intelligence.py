"""Add investment candidate onboarding and autonomous exploration.

Revision ID: 20260722_01
Revises: b4c000000005
Create Date: 2026-07-22

Integrated automatically against Alembic head b4c000000005.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_01"
down_revision: str | None = "b4c000000005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exploration_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("strategy_codes", postgresql.JSONB(), nullable=False),
        sa.Column("requested_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("minimum_liquidity", sa.Numeric(24, 6), nullable=False),
        sa.Column("maximum_suggestions", sa.Integer(), nullable=False),
        sa.Column("excluded_instrument_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("workflow_id", sa.String(255), unique=True),
        sa.Column("universe_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("eligible_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_detail", sa.Text()),
        sa.CheckConstraint("status IN ('queued','running','succeeded','partial','failed','cancelled')", name="ck_exploration_runs_status_values"),
        sa.CheckConstraint("minimum_liquidity >= 0", name="ck_exploration_runs_nonnegative_liquidity"),
        sa.CheckConstraint("maximum_suggestions BETWEEN 1 AND 100", name="ck_exploration_runs_suggestion_limit"),
    )
    op.create_index("ix_exploration_runs_org_created", "exploration_runs", ["organization_id", sa.text("created_at DESC")])
    op.create_index("ix_exploration_runs_status", "exploration_runs", ["status"])

    op.create_table(
        "exploration_suggestions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("exploration_run_id", sa.Uuid(), sa.ForeignKey("exploration_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("issuer_id", sa.Uuid(), sa.ForeignKey("issuers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("ticker", sa.String(24), nullable=False),
        sa.Column("exchange", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("quantitative_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("data_coverage_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("source_discovery_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("signals", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("risks", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("promoted_candidate_id", sa.Uuid()),
        sa.Column("dismissed_at", sa.DateTime(timezone=True)),
        sa.Column("dismissed_by", sa.String(255)),
        sa.Column("dismissal_reason", sa.Text()),
        sa.UniqueConstraint("exploration_run_id", "instrument_id", name="uq_exploration_suggestion_instrument"),
        sa.CheckConstraint("status IN ('new','promoted','dismissed','duplicate','expired')", name="ck_exploration_suggestions_status_values"),
        sa.CheckConstraint(
            "quantitative_score BETWEEN 0 AND 1 AND data_coverage_score BETWEEN 0 AND 1 AND source_discovery_score BETWEEN 0 AND 1",
            name="ck_exploration_suggestions_score_ranges",
        ),
        sa.CheckConstraint(
            "status <> 'dismissed' OR (dismissed_at IS NOT NULL AND dismissed_by IS NOT NULL AND dismissal_reason IS NOT NULL)",
            name="ck_exploration_suggestions_dismissal_fields",
        ),
    )
    op.create_index("ix_exploration_suggestions_org_status", "exploration_suggestions", ["organization_id", "status"])

    op.create_table(
        "investment_candidates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("origin", sa.String(20), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("ticker", sa.String(24), nullable=False),
        sa.Column("exchange", sa.String(20), nullable=False, server_default="B3"),
        sa.Column("legal_name", sa.String(300)),
        sa.Column("trading_name", sa.String(300)),
        sa.Column("cnpj", sa.String(32)),
        sa.Column("cvm_code", sa.String(32)),
        sa.Column("issuer_id", sa.Uuid(), sa.ForeignKey("issuers.id", ondelete="RESTRICT")),
        sa.Column("instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id", ondelete="RESTRICT")),
        sa.Column("rationale", sa.Text()),
        sa.Column("exploration_suggestion_id", sa.Uuid(), sa.ForeignKey("exploration_suggestions.id", ondelete="SET NULL")),
        sa.Column("final_decision", sa.String(20)),
        sa.Column("final_decision_reason", sa.Text()),
        sa.Column("approved_portfolio_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("origin IN ('manual','explorer')", name="ck_investment_candidates_origin_values"),
        sa.CheckConstraint(
            "status IN ('suggested','identity_resolution','source_discovery','awaiting_user_input','source_validation','document_collection','data_quality','fundamental_analysis','risk_analysis','committee_review','approved','rejected','watchlist','cancelled')",
            name="ck_investment_candidates_status_values",
        ),
        sa.CheckConstraint("final_decision IS NULL OR final_decision IN ('approve','reject','pending','watchlist')", name="ck_investment_candidates_final_decision_values"),
        sa.CheckConstraint("lock_version > 0", name="ck_investment_candidates_positive_lock_version"),
        sa.CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="ck_investment_candidates_request_hash_format"),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_candidate_org_idempotency"),
    )
    op.create_index("ix_investment_candidates_org_status", "investment_candidates", ["organization_id", "status"])
    op.create_index(
        "uq_candidate_active_ticker",
        "investment_candidates",
        ["organization_id", "exchange", "ticker"],
        unique=True,
        postgresql_where=sa.text("status <> 'cancelled'"),
    )

    op.create_foreign_key(
        "fk_exploration_suggestions_promoted_candidate",
        "exploration_suggestions",
        "investment_candidates",
        ["promoted_candidate_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "candidate_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("investment_candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("normalized_url_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("verification_method", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("official", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("discovered_by", sa.String(255), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("candidate_id", "kind", "normalized_url_hash", name="uq_candidate_source_kind_url"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_candidate_sources_confidence_range"),
        sa.CheckConstraint("status IN ('discovered','verified','rejected','stale','unreachable')", name="ck_candidate_sources_status_values"),
        sa.CheckConstraint("NOT (official AND verification_method = 'agent_inference')", name="ck_candidate_sources_agent_cannot_confirm_official"),
        sa.CheckConstraint("status <> 'verified' OR verified_at IS NOT NULL", name="ck_candidate_sources_verified_timestamp"),
    )
    op.create_index("ix_candidate_sources_candidate_kind", "candidate_sources", ["candidate_id", "kind"])

    op.create_table(
        "candidate_gaps",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("investment_candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.String(40)),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("requested_user_action", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by", sa.String(255)),
        sa.Column("resolution_notes", sa.Text()),
        sa.CheckConstraint("level IN ('blocking','required','optional')", name="ck_candidate_gaps_level_values"),
        sa.CheckConstraint("status IN ('open','resolved','waived')", name="ck_candidate_gaps_status_values"),
        sa.CheckConstraint("status = 'open' OR (resolved_at IS NOT NULL AND resolved_by IS NOT NULL)", name="ck_candidate_gaps_resolution_fields"),
    )
    op.create_index(
        "uq_candidate_open_gap_code",
        "candidate_gaps",
        ["candidate_id", "code"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )

    op.create_table(
        "candidate_analysis_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("investment_candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("trigger", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("requested_by", sa.String(255), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("workflow_id", sa.String(255), unique=True),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("decision", sa.String(20)),
        sa.Column("summary", sa.Text()),
        sa.Column("blocker_codes", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("agent_run_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("research_case_id", sa.Uuid(), sa.ForeignKey("research_cases.id", ondelete="SET NULL")),
        sa.Column("thesis_version_id", sa.Uuid()),
        sa.Column("committee_decision_id", sa.Uuid()),
        sa.Column("error_code", sa.String(100)),
        sa.Column("error_detail", sa.Text()),
        sa.UniqueConstraint("candidate_id", "run_number", name="uq_candidate_analysis_run_number"),
        sa.CheckConstraint("run_number > 0", name="ck_candidate_analysis_runs_positive_number"),
        sa.CheckConstraint("status IN ('queued','running','blocked','succeeded','failed','cancelled')", name="ck_candidate_analysis_runs_status_values"),
        sa.CheckConstraint("decision IS NULL OR decision IN ('approve','reject','pending','watchlist')", name="ck_candidate_analysis_runs_decision_values"),
    )
    op.create_index("ix_candidate_analysis_runs_candidate_status", "candidate_analysis_runs", ["candidate_id", "status"])

    op.create_table(
        "candidate_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("investment_candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("actor_type", sa.String(30), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("aggregate_version > 0", name="ck_candidate_events_positive_version"),
    )
    op.create_index("ix_candidate_event_timeline", "candidate_events", ["candidate_id", sa.text("occurred_at DESC")])


def downgrade() -> None:
    op.drop_table("candidate_events")
    op.drop_table("candidate_analysis_runs")
    op.drop_table("candidate_gaps")
    op.drop_table("candidate_sources")
    op.drop_constraint("fk_exploration_suggestions_promoted_candidate", "exploration_suggestions", type_="foreignkey")
    op.drop_table("investment_candidates")
    op.drop_table("exploration_suggestions")
    op.drop_table("exploration_runs")
