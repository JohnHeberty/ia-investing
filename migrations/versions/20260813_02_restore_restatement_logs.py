"""Restore the restatement audit table omitted from the migration chain.

Revision ID: 20260813_02
Revises: 20260813_01
Create Date: 2026-08-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260813_02"
down_revision: str | Sequence[str] | None = "20260813_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "restatement_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("superseded_fact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("new_fact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("account_code", sa.String(100), nullable=False),
        sa.Column("old_value", sa.Numeric(28, 8), nullable=True),
        sa.Column("new_value", sa.Numeric(28, 8), nullable=True),
        sa.Column("old_value_status", sa.String(20), nullable=True),
        sa.Column("new_value_status", sa.String(20), nullable=True),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_restatement_logs"),
        sa.ForeignKeyConstraint(
            ["superseded_fact_id"],
            ["financial_facts.id"],
            name="fk_restatement_logs_superseded_fact_id_financial_facts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["new_fact_id"],
            ["financial_facts.id"],
            name="fk_restatement_logs_new_fact_id_financial_facts",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("revision_number > 0", name="ck_restatement_logs_positive_revision_number"),
    )
    op.create_index("ix_restatement_logs_superseded_fact_id", "restatement_logs", ["superseded_fact_id"])
    op.create_index("ix_restatement_logs_new_fact_id", "restatement_logs", ["new_fact_id"])


def downgrade() -> None:
    op.drop_table("restatement_logs")
