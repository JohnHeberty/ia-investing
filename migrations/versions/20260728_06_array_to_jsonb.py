"""Convert document_chunks.section_path from ARRAY to JSONB.

Revision ID: 20260728_06
Revises: 20260728_05
Create Date: 2026-07-28

JSONB is more efficient for querying array elements and avoids the
known PostgreSQL issue where ARRAY type is lost across views.
"""

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_06"
down_revision: str | None = "20260728_05"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.alter_column(
        "document_chunks",
        "section_path",
        existing_type=sa.ARRAY(sa.Text),
        type_=sa.JSON,
        server_default="[]",
        existing_server_default="{}",
    )


def downgrade() -> None:
    op.alter_column(
        "document_chunks",
        "section_path",
        existing_type=sa.JSON,
        type_=sa.ARRAY(sa.Text),
        server_default="{}",
    )
