"""Merge branch heads: 20260727_02 and 20260728_03.

Revision ID: 20260728_merge
Revises: 20260727_02, 20260728_03
Create Date: 2026-07-28
"""


revision: str = "20260728_merge"
down_revision: tuple = ("20260727_02", "20260728_03")
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
