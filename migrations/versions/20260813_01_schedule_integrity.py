"""Add schedule-history and event-deduplication integrity constraints.

Revision ID: 20260813_01
Revises: 20260812_02
Create Date: 2026-08-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260813_01"
down_revision: str | Sequence[str] | None = "20260812_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM event_duplicates newer
        USING event_duplicates older
        WHERE newer.duplicate_id = older.duplicate_id
          AND (newer.created_at, newer.id) > (older.created_at, older.id)
        """
    )
    op.create_unique_constraint(
        "uq_event_duplicates_duplicate_id",
        "event_duplicates",
        ["duplicate_id"],
    )

    op.execute(
        """
        DELETE FROM schedule_run_history newer
        USING schedule_run_history older
        WHERE newer.schedule_id = older.schedule_id
          AND newer.workflow_id = older.workflow_id
          AND (newer.created_at, newer.id) > (older.created_at, older.id)
        """
    )
    op.create_check_constraint(
        "ck_schedule_run_history_status",
        "schedule_run_history",
        "status IN ('running','completed','failed')",
    )
    op.create_unique_constraint(
        "uq_schedule_run_history_schedule_workflow",
        "schedule_run_history",
        ["schedule_id", "workflow_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_schedule_run_history_schedule_workflow",
        "schedule_run_history",
        type_="unique",
    )
    op.drop_constraint("ck_schedule_run_history_status", "schedule_run_history", type_="check")
    op.drop_constraint("uq_event_duplicates_duplicate_id", "event_duplicates", type_="unique")
