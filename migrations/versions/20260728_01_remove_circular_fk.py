"""Remove circular FK between investment_candidates and exploration_suggestions.

Revision ID: 20260728_01
Revises: 20260727_01
Create Date: 2026-07-28

- R4-12: Drop FK constraint fk_exploration_suggestions_promoted_candidate
  to break circular dependency between investment_candidates and exploration_suggestions.
  The promoted_candidate_id column is retained as a regular indexed column.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260728_01"
down_revision: str | None = "20260727_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop the circular FK constraint (column remains, just no FK)
    op.execute(
        "ALTER TABLE exploration_suggestions DROP CONSTRAINT IF EXISTS fk_exploration_suggestions_promoted_candidate"
    )


def downgrade() -> None:
    # Re-create the FK constraint
    op.execute(
        "DELETE FROM exploration_suggestions "
        "WHERE promoted_candidate_id IS NOT NULL "
        "AND promoted_candidate_id NOT IN (SELECT id FROM investment_candidates)"
    )
    op.execute(
        "ALTER TABLE exploration_suggestions "
        "ADD CONSTRAINT fk_exploration_suggestions_promoted_candidate "
        "FOREIGN KEY (promoted_candidate_id) REFERENCES investment_candidates(id) "
        "ON DELETE SET NULL"
    )
