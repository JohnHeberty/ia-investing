"""Convert document_chunks.section_path from ARRAY to JSONB.

Revision ID: 20260728_06
Revises: 20260728_05
Create Date: 2026-07-28

JSONB is more efficient for querying array elements and avoids the
known PostgreSQL issue where ARRAY type is lost across views.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_06"
down_revision: str | None = "20260728_05"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    # Check if table exists and has section_path column
    result = conn.execute(
        sa.text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.columns "
            "  WHERE table_name = 'document_chunks' AND column_name = 'section_path'"
            ")"
        )
    )
    if not result.scalar():
        return
    op.execute(
        "ALTER TABLE document_chunks ALTER COLUMN section_path "
        "TYPE json USING section_path::text::json"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE document_chunks ALTER COLUMN section_path "
        "TYPE text[] USING section_path::text[]"
    )
