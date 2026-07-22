"""add committee sessions, votes, decisions and executions tables

Revision ID: b4c000000004
Revises: b4c000000003

Creates tables for committee deliberation workflow and execution management:
- committee_sessions: state-machine-driven deliberation sessions
- committee_votes: per-member votes on proposals
- committee_decisions: published decisions with vote summaries
- executions: order execution lifecycle with state machine
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "b4c000000004"
down_revision: str | Sequence[str] | None = "b4c000000003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- committee_sessions ---
    op.create_table(
        "committee_sessions",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("thesis_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("members", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("convened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("agenda", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("total_members", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("present_members", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("votes_in_favor", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("votes_against", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("members_notified", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("decision", sa.Text, nullable=True),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_committee_sessions"),
        sa.CheckConstraint(
            "state IN ('scheduled','in_session','voting','deliberating','decided','published','archived')",
            name="ck_committee_session_state",
        ),
        sa.CheckConstraint("total_members >= 0", name="ck_committee_session_total_members"),
        sa.CheckConstraint("present_members >= 0", name="ck_committee_session_present_members"),
        sa.CheckConstraint("votes_in_favor >= 0", name="ck_committee_session_votes_in_favor"),
        sa.CheckConstraint("votes_against >= 0", name="ck_committee_session_votes_against"),
    )

    # --- committee_votes ---
    op.create_table(
        "committee_votes",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("member_id", sa.String(100), nullable=False),
        sa.Column("proposal_id", sa.String(100), nullable=False),
        sa.Column("vote", sa.String(20), nullable=False),
        sa.Column("justification", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["committee_sessions.id"],
            ondelete="CASCADE",
            name="fk_committee_votes_session_id_committee_sessions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_committee_votes"),
        sa.UniqueConstraint(
            "session_id",
            "member_id",
            "proposal_id",
            name="uq_committee_vote_session_member_proposal",
        ),
        sa.CheckConstraint(
            "vote IN ('in_favor','against','abstain')",
            name="ck_committee_vote_value",
        ),
    )
    op.create_index(
        "ix_committee_votes_session_id",
        "committee_votes",
        ["session_id"],
    )

    # --- committee_decisions ---
    op.create_table(
        "committee_decisions",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.Text, nullable=False),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column("votes_summary", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["committee_sessions.id"],
            ondelete="CASCADE",
            name="fk_committee_decisions_session_id_committee_sessions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_committee_decisions"),
        sa.UniqueConstraint("session_id", name="uq_committee_decisions_session_id"),
    )
    op.create_index(
        "ix_committee_decisions_session_id",
        "committee_decisions",
        ["session_id"],
    )

    # --- executions ---
    op.create_table(
        "executions",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id", sa.String(100), nullable=False),
        sa.Column("portfolio_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 4), nullable=False),
        sa.Column("price_limit", sa.Numeric(14, 6), nullable=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("available_balance", sa.Numeric(20, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("required_amount", sa.Numeric(20, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("alert_triggered", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("filled_quantity", sa.Numeric(20, 4), nullable=True),
        sa.Column("avg_price", sa.Numeric(14, 6), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolios.id"],
            ondelete="RESTRICT",
            name="fk_executions_portfolio_id_portfolios",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_executions"),
        sa.CheckConstraint("action IN ('buy','sell')", name="ck_execution_action"),
        sa.CheckConstraint(
            "state IN ('pending','validated','queued','dispatched','confirmed','failed','settled')",
            name="ck_execution_state",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_execution_quantity_positive"),
        sa.CheckConstraint("available_balance >= 0", name="ck_execution_available_balance_nonnegative"),
        sa.CheckConstraint("required_amount >= 0", name="ck_execution_required_amount_nonnegative"),
    )
    op.create_index("ix_executions_order_id", "executions", ["order_id"])
    op.create_index("ix_executions_portfolio_id", "executions", ["portfolio_id"])
    op.create_index(
        "ix_executions_portfolio_state",
        "executions",
        ["portfolio_id", "state"],
    )
    op.create_index(
        "ix_executions_state_created",
        "executions",
        ["state", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_executions_state_created", table_name="executions")
    op.drop_index("ix_executions_portfolio_state", table_name="executions")
    op.drop_index("ix_executions_portfolio_id", table_name="executions")
    op.drop_index("ix_executions_order_id", table_name="executions")
    op.drop_table("executions")
    op.drop_index("ix_committee_decisions_session_id", table_name="committee_decisions")
    op.drop_table("committee_decisions")
    op.drop_index("ix_committee_votes_session_id", table_name="committee_votes")
    op.drop_table("committee_votes")
    op.drop_table("committee_sessions")
