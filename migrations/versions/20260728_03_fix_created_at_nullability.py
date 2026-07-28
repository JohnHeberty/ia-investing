"""R5-20: Fix created_at nullability — all created_at should be NOT NULL.

Revision ID: 20260728_03
Revises: 20260728_02
Create Date: 2026-07-28
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260728_03"
down_revision: str | None = "20260728_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables where created_at is nullable but should be NOT NULL
_TABLES_WITH_NULLABLE_CREATED_AT = [
    "issuers",
    "documents",
    "workflows",
    "quality_checks",
    "financial_facts",
    "theses",
    "thesis_versions",
    "processing_jobs",
    "universes",
    "detected_events",
    "news_articles",
    "data_sources",
    "source_slas",
    "portfolios",
    "positions",
    "recommendations",
    "agent_assessments",
]


def upgrade() -> None:
    for table in _TABLES_WITH_NULLABLE_CREATED_AT:
        op.execute(
            f"UPDATE {table} SET created_at = NOW() WHERE created_at IS NULL"  # noqa: S608
        )
        op.alter_column(
            table,
            "created_at",
            nullable=False,
        )


def downgrade() -> None:
    for table in reversed(_TABLES_WITH_NULLABLE_CREATED_AT):
        op.alter_column(
            table,
            "created_at",
            nullable=True,
        )
