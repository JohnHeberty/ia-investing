"""Add UNIQUE constraints to news tables for idempotency.

Revision ID: f7a100000009
Revises: 20260730_01
Create Date: 2026-08-03
"""

from alembic import op

revision = "f7a100000009"
down_revision = "20260730_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_news_sources_name",
        "news_sources",
        ["name"],
    )
    op.create_unique_constraint(
        "uq_news_entity_links_item_issuer",
        "news_entity_links",
        ["news_item_id", "issuer_id"],
    )
    op.create_unique_constraint(
        "uq_event_duplicates_original_duplicate",
        "event_duplicates",
        ["original_id", "duplicate_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_event_duplicates_original_duplicate", "event_duplicates", type_="unique")
    op.drop_constraint("uq_news_entity_links_item_issuer", "news_entity_links", type_="unique")
    op.drop_constraint("uq_news_sources_name", "news_sources", type_="unique")
