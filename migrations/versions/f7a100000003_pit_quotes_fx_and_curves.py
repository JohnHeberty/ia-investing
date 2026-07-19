"""add point-in-time quotes, FX rates, and yield curves

Revision ID: f7a100000003
Revises: f7a100000002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a100000003"
down_revision: str | Sequence[str] | None = "f7a100000002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_quotes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("listing_id", sa.UUID(), nullable=False),
        sa.Column("quoted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bid_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("ask_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("last_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("source_object_version_id", sa.UUID(), nullable=False),
        sa.Column("knowledge_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "bid_price IS NOT NULL OR ask_price IS NOT NULL OR last_price IS NOT NULL",
            name=op.f("ck_market_quotes_at_least_one_price"),
        ),
        sa.CheckConstraint(
            "bid_price IS NULL OR ask_price IS NULL OR bid_price <= ask_price",
            name=op.f("ck_market_quotes_valid_spread"),
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"], ["listings.id"], name=op.f("fk_market_quotes_listing_id_listings"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_object_version_id"],
            ["source_object_versions.id"],
            name=op.f("fk_market_quotes_source_object_version_id_source_object_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_quotes")),
        sa.UniqueConstraint("listing_id", "quoted_at", "knowledge_at", name="uq_market_quotes_pit"),
    )
    op.create_index(op.f("ix_market_quotes_listing_id"), "market_quotes", ["listing_id"])
    op.create_index(op.f("ix_market_quotes_quoted_at"), "market_quotes", ["quoted_at"])
    op.create_index(op.f("ix_market_quotes_knowledge_at"), "market_quotes", ["knowledge_at"])
    op.create_table(
        "fx_rates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("quote_currency", sa.String(3), nullable=False),
        sa.Column("rate_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rate", sa.Numeric(28, 12), nullable=False),
        sa.Column("source_object_version_id", sa.UUID(), nullable=False),
        sa.Column("knowledge_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("base_currency ~ '^[A-Z]{3}$'", name=op.f("ck_fx_rates_base_currency_format")),
        sa.CheckConstraint("quote_currency ~ '^[A-Z]{3}$'", name=op.f("ck_fx_rates_quote_currency_format")),
        sa.CheckConstraint("base_currency <> quote_currency", name=op.f("ck_fx_rates_different_currencies")),
        sa.CheckConstraint("rate > 0", name=op.f("ck_fx_rates_positive_rate")),
        sa.ForeignKeyConstraint(
            ["source_object_version_id"],
            ["source_object_versions.id"],
            name=op.f("fk_fx_rates_source_object_version_id_source_object_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fx_rates")),
        sa.UniqueConstraint("base_currency", "quote_currency", "rate_at", "knowledge_at", name="uq_fx_rates_pit"),
    )
    op.create_index(op.f("ix_fx_rates_rate_at"), "fx_rates", ["rate_at"])
    op.create_index(op.f("ix_fx_rates_knowledge_at"), "fx_rates", ["knowledge_at"])
    op.create_table(
        "yield_curve_points",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("curve_code", sa.String(50), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("tenor_days", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("annual_rate", sa.Numeric(18, 12), nullable=False),
        sa.Column("source_object_version_id", sa.UUID(), nullable=False),
        sa.Column("knowledge_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name=op.f("ck_yield_curve_points_currency_code_format")),
        sa.CheckConstraint("tenor_days > 0", name=op.f("ck_yield_curve_points_positive_tenor")),
        sa.CheckConstraint("annual_rate > -1", name=op.f("ck_yield_curve_points_supported_rate_domain")),
        sa.ForeignKeyConstraint(
            ["source_object_version_id"],
            ["source_object_versions.id"],
            name=op.f("fk_yield_curve_points_source_object_version_id_source_object_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_yield_curve_points")),
        sa.UniqueConstraint(
            "curve_code", "tenor_days", "observed_at", "knowledge_at", name="uq_yield_curve_points_pit"
        ),
    )
    op.create_index(op.f("ix_yield_curve_points_observed_at"), "yield_curve_points", ["observed_at"])
    op.create_index(op.f("ix_yield_curve_points_knowledge_at"), "yield_curve_points", ["knowledge_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_yield_curve_points_knowledge_at"), table_name="yield_curve_points")
    op.drop_index(op.f("ix_yield_curve_points_observed_at"), table_name="yield_curve_points")
    op.drop_table("yield_curve_points")
    op.drop_index(op.f("ix_fx_rates_knowledge_at"), table_name="fx_rates")
    op.drop_index(op.f("ix_fx_rates_rate_at"), table_name="fx_rates")
    op.drop_table("fx_rates")
    op.drop_index(op.f("ix_market_quotes_knowledge_at"), table_name="market_quotes")
    op.drop_index(op.f("ix_market_quotes_quoted_at"), table_name="market_quotes")
    op.drop_index(op.f("ix_market_quotes_listing_id"), table_name="market_quotes")
    op.drop_table("market_quotes")
