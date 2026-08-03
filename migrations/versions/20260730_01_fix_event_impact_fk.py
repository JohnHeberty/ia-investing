"""Fix EventImpact FK: investment_theses → research_theses.

The investment_theses table was dropped in 20260728_04 but EventImpact
still references it. This migration recreates the FK to research_theses.

Revision ID: 20260730_01
Revises: 20260729_01
Create Date: 2026-07-30
"""

from alembic import op

revision = "20260730_01"
down_revision = "20260729_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE event_impacts DROP CONSTRAINT IF EXISTS event_impacts_thesis_id_fkey"
    )
    op.execute(
        "ALTER TABLE event_impacts ADD CONSTRAINT event_impacts_thesis_id_fkey "
        "FOREIGN KEY (thesis_id) REFERENCES research_theses(id) ON DELETE SET NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE event_impacts DROP CONSTRAINT IF EXISTS event_impacts_thesis_id_fkey"
    )
    op.execute(
        "ALTER TABLE event_impacts ADD CONSTRAINT event_impacts_thesis_id_fkey "
        "FOREIGN KEY (thesis_id) REFERENCES investment_theses(id) ON DELETE SET NULL"
    )
