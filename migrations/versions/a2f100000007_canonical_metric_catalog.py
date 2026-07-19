"""seed versioned canonical metric definitions

Revision ID: a2f100000007
Revises: a2f100000006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a2f100000007"
down_revision: str | Sequence[str] | None = "a2f100000006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = sa.table(
        "metric_definitions",
        sa.column("id", sa.UUID()),
        sa.column("name", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("formula", sa.Text()),
        sa.column("unit", sa.String()),
        sa.column("frequency", sa.String()),
        sa.column("dependencies", sa.JSON()),
    )
    op.bulk_insert(
        table,
        [
            {
                "id": "50000000-0000-0000-0000-000000000001",
                "name": "current_ratio",
                "version": 1,
                "formula": "current_assets / current_liabilities",
                "unit": "ratio",
                "frequency": "quarterly",
                "dependencies": ["current_assets", "current_liabilities"],
            },
            {
                "id": "50000000-0000-0000-0000-000000000002",
                "name": "net_margin",
                "version": 1,
                "formula": "net_income / revenue",
                "unit": "ratio",
                "frequency": "quarterly",
                "dependencies": ["net_income", "revenue"],
            },
            {
                "id": "50000000-0000-0000-0000-000000000003",
                "name": "debt_to_equity",
                "version": 1,
                "formula": "total_debt / equity",
                "unit": "ratio",
                "frequency": "quarterly",
                "dependencies": ["total_debt", "equity"],
            },
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM metric_definitions WHERE version = 1 "
            "AND name IN ('current_ratio', 'net_margin', 'debt_to_equity')"
        )
    )
