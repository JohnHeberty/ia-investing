"""Add schedule run history table.

Revision ID: f7a100000011
Revises: f7a100000010
Create Date: 2026-08-03
"""

import sqlalchemy as sa
from alembic import op

revision = "f7a100000011"
down_revision = "f7a100000010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schedule_run_history",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("schedule_id", sa.String(200), nullable=False),
        sa.Column("workflow_id", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_schedule_run_history_schedule_id", "schedule_run_history", ["schedule_id"])
    op.create_index("ix_schedule_run_history_started_at", "schedule_run_history", [sa.text("started_at DESC")])


def downgrade() -> None:
    op.drop_index("ix_schedule_run_history_started_at", table_name="schedule_run_history")
    op.drop_index("ix_schedule_run_history_schedule_id", table_name="schedule_run_history")
    op.drop_table("schedule_run_history")
