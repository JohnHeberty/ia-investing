"""Add performance indexes for news tables.

Revision ID: f7a100000010
Revises: f7a100000009
Create Date: 2026-08-03
"""

from alembic import op

revision = "f7a100000010"
down_revision = "f7a100000009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # GIN index on raw_data JSONB for fast content_hash lookups in _load_existing_hashes
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_news_items_raw_data_hash "
        "ON news_items USING gin (raw_data jsonb_path_ops)"
    )

    # B-tree index on DetectedEvent.news_item_id for idempotency guard in analyze_news_item
    op.create_index(
        "ix_detected_events_news_item_id",
        "detected_events",
        ["news_item_id"],
    )

    # B-tree index on DetectedEvent.issuer_id for list_detected_events filtering
    op.create_index(
        "ix_detected_events_issuer_id",
        "detected_events",
        ["issuer_id"],
    )

    # B-tree index on NewsItem.is_processed for filtered listing
    op.create_index(
        "ix_news_items_is_processed",
        "news_items",
        ["is_processed"],
    )

    # Composite index on DetectedEvent for duplicate detection query
    op.create_index(
        "ix_detected_events_type_issuer_created",
        "detected_events",
        ["event_type", "issuer_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_detected_events_type_issuer_created", table_name="detected_events")
    op.drop_index("ix_news_items_is_processed", table_name="news_items")
    op.drop_index("ix_detected_events_issuer_id", table_name="detected_events")
    op.drop_index("ix_detected_events_news_item_id", table_name="detected_events")
    op.execute("DROP INDEX IF EXISTS ix_news_items_raw_data_hash")
