"""Grant application access to schedule run history.

Revision ID: 20260813_04
Revises: 20260813_03
Create Date: 2026-08-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260813_04"
down_revision: str | Sequence[str] | None = "20260813_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE schedule_run_history TO app;
            END IF;
        END $$
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app') THEN
                REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLE schedule_run_history FROM app;
            END IF;
        END $$
        """
    )
