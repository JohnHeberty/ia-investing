"""seed versioned canonical metric definitions

Revision ID: a2f100000007
Revises: a2f100000006
"""

from collections.abc import Sequence

revision: str = "a2f100000007"
down_revision: str | Sequence[str] | None = "a2f100000006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Seed data moved to scripts/seed_initial_data.py — run `make init`.
    pass


def downgrade() -> None:
    # Seed data removed from migrations — managed by scripts/seed_initial_data.py.
    pass
