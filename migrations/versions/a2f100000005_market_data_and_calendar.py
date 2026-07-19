"""point-in-time market data, corporate actions, and calendar

Revision ID: a2f100000005
Revises: a2f100000004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a2f100000005"
down_revision: str | Sequence[str] | None = "a2f100000004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_indices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_indices")),
        sa.UniqueConstraint("code", name=op.f("uq_market_indices_code")),
    )
    op.create_table(
        "trading_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("market_code", sa.String(20), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("is_open", sa.Boolean(), nullable=False),
        sa.Column("opens_at", sa.Time(timezone=True), nullable=True),
        sa.Column("closes_at", sa.Time(timezone=True), nullable=True),
        sa.Column("reason", sa.String(200), nullable=True),
        sa.Column("calendar_version", sa.String(50), nullable=False),
        sa.Column("knowledge_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(is_open AND opens_at IS NOT NULL AND closes_at IS NOT NULL) OR "
            "(NOT is_open AND opens_at IS NULL AND closes_at IS NULL)",
            name=op.f("ck_trading_sessions_hours_match_open_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trading_sessions")),
        sa.UniqueConstraint("market_code", "session_date", "calendar_version", name="uq_trading_sessions_version"),
    )
    op.create_table(
        "market_bars",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("listing_id", sa.UUID(), nullable=False),
        sa.Column("interval", sa.String(10), nullable=False),
        sa.Column("bar_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("high_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("low_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("close_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("source_object_version_id", sa.UUID(), nullable=False),
        sa.Column("knowledge_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("high_price >= low_price", name=op.f("ck_market_bars_valid_high_low")),
        sa.CheckConstraint("volume >= 0", name=op.f("ck_market_bars_nonnegative_volume")),
        sa.ForeignKeyConstraint(
            ["listing_id"], ["listings.id"], name=op.f("fk_market_bars_listing_id_listings"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_object_version_id"],
            ["source_object_versions.id"],
            name=op.f("fk_market_bars_source_object_version_id_source_object_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_bars")),
        sa.UniqueConstraint("listing_id", "interval", "bar_at", "knowledge_at", name="uq_market_bars_pit"),
    )
    op.create_index(op.f("ix_market_bars_knowledge_at"), "market_bars", ["knowledge_at"])
    op.create_index(op.f("ix_market_bars_listing_id"), "market_bars", ["listing_id"])
    op.create_table(
        "corporate_actions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("instrument_id", sa.UUID(), nullable=False),
        sa.Column("action_type", sa.String(30), nullable=False),
        sa.Column("announcement_date", sa.Date(), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=True),
        sa.Column("record_date", sa.Date(), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("amount_per_unit", sa.Numeric(20, 8), nullable=True),
        sa.Column("ratio", sa.Numeric(20, 10), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=True),
        sa.Column("source_object_version_id", sa.UUID(), nullable=False),
        sa.Column("knowledge_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action_type IN ('dividend', 'jcp', 'split', 'reverse_split', 'subscription', 'buyback', 'bonus')",
            name=op.f("ck_corporate_actions_action_type_values"),
        ),
        sa.CheckConstraint(
            "amount_per_unit IS NULL OR amount_per_unit >= 0",
            name=op.f("ck_corporate_actions_nonnegative_amount"),
        ),
        sa.CheckConstraint("ratio IS NULL OR ratio > 0", name=op.f("ck_corporate_actions_positive_ratio")),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name=op.f("fk_corporate_actions_instrument_id_instruments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_object_version_id"],
            ["source_object_versions.id"],
            name=op.f("fk_corporate_actions_source_object_version_id_source_object_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_corporate_actions")),
        sa.UniqueConstraint(
            "instrument_id",
            "action_type",
            "announcement_date",
            "ex_date",
            "knowledge_at",
            name="uq_corporate_actions_pit",
        ),
    )
    op.create_index(op.f("ix_corporate_actions_instrument_id"), "corporate_actions", ["instrument_id"])
    op.create_table(
        "index_constituents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("index_id", sa.UUID(), nullable=False),
        sa.Column("instrument_id", sa.UUID(), nullable=False),
        sa.Column("weight", sa.Numeric(10, 8), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("knowledge_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name=op.f("ck_index_constituents_valid_window"),
        ),
        sa.CheckConstraint("weight IS NULL OR weight BETWEEN 0 AND 1", name=op.f("ck_index_constituents_weight_range")),
        sa.ForeignKeyConstraint(
            ["index_id"],
            ["market_indices.id"],
            name=op.f("fk_index_constituents_index_id_market_indices"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name=op.f("fk_index_constituents_instrument_id_instruments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_index_constituents")),
        sa.UniqueConstraint(
            "index_id", "instrument_id", "valid_from", "knowledge_at", name="uq_index_constituents_pit"
        ),
    )
    op.create_index(op.f("ix_index_constituents_index_id"), "index_constituents", ["index_id"])
    op.create_index(op.f("ix_index_constituents_instrument_id"), "index_constituents", ["instrument_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_index_constituents_instrument_id"), table_name="index_constituents")
    op.drop_index(op.f("ix_index_constituents_index_id"), table_name="index_constituents")
    op.drop_table("index_constituents")
    op.drop_index(op.f("ix_corporate_actions_instrument_id"), table_name="corporate_actions")
    op.drop_table("corporate_actions")
    op.drop_index(op.f("ix_market_bars_listing_id"), table_name="market_bars")
    op.drop_index(op.f("ix_market_bars_knowledge_at"), table_name="market_bars")
    op.drop_table("market_bars")
    op.drop_table("trading_sessions")
    op.drop_table("market_indices")
