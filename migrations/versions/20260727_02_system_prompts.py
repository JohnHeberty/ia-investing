"""Create system_prompts table + FK on agent_definitions.

Revision ID: 20260727_02
Revises: 20260727_01
Create Date: 2026-07-27

- R5-8: Create system_prompts table, add FK on agent_definitions.system_prompt_id
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260727_02"
down_revision: str | None = "20260727_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_prompts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_foreign_key(
        "fk_agent_definitions_system_prompt",
        "agent_definitions",
        "system_prompts",
        ["system_prompt_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_agent_definitions_system_prompt", "agent_definitions", type_="foreignkey")
    op.drop_table("system_prompts")
