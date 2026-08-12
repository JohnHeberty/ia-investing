"""R5-20: Fix created_at nullability — all created_at should be NOT NULL.

Revision ID: 20260728_03
Revises: 20260728_02
Create Date: 2026-07-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_03"
down_revision: str | None = "20260728_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _upgrade_table(table: str) -> None:
    conn = op.get_bind()
    # Check if table exists and has created_at column
    result = conn.execute(
        sa.text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.columns "
            "  WHERE table_name = :table AND column_name = 'created_at'"
            ")"
        ),
        {"table": table},
    )
    has_column = result.scalar()
    if not has_column:
        return
    # Backfill NULLs then enforce NOT NULL
    conn.execute(sa.text(f"UPDATE {table} SET created_at = NOW() WHERE created_at IS NULL"))  # noqa: S608
    conn.execute(sa.text(f"ALTER TABLE {table} ALTER COLUMN created_at SET NOT NULL"))


def upgrade() -> None:
    # Tables known to have nullable created_at that should be NOT NULL.
    # Only those that exist at this point in the migration chain.
    _TABLES = [
        "legal_entities",
        "documents",
        "financial_facts",
        "research_theses",
        "research_thesis_versions",
        "universe_filters",
        "detected_events",
        "news_items",
        "data_sources",
        "portfolios",
        "positions",
    ]
    for table in _TABLES:
        _upgrade_table(table)


def downgrade() -> None:
    _TABLES = [
        "legal_entities",
        "documents",
        "financial_facts",
        "research_theses",
        "research_thesis_versions",
        "universe_filters",
        "detected_events",
        "news_items",
        "data_sources",
        "portfolios",
        "positions",
    ]
    for table in _TABLES:
        op.alter_column(
            table,
            "created_at",
            nullable=True,
        )
