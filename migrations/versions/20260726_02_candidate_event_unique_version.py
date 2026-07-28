"""Add unique constraint on candidate_events(candidate_id, aggregate_version).

Revision ID: 20260726_02
Revises: 20260726_01
Create Date: 2026-07-26

Enforces monotonic aggregate_version per candidate (P0-13 fix).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260726_02"
down_revision: str | None = "20260726_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_candidate_event_candidate_version",
        "candidate_events",
        ["candidate_id", "aggregate_version"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_candidate_event_candidate_version",
        "candidate_events",
        type_="unique",
    )
