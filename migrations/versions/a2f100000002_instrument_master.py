"""temporal instrument master

Revision ID: a2f100000002
Revises: a2f100000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a2f100000002"
down_revision: str | Sequence[str] | None = "a2f100000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_table(
        "legal_entities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("legal_name", sa.String(300), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("tax_identifier", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("country_code ~ '^[A-Z]{2}$'", name=op.f("ck_legal_entities_country_code_format")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_legal_entities")),
        sa.UniqueConstraint("country_code", "tax_identifier", name="uq_legal_entities_country_tax_id"),
    )
    op.create_table(
        "instruments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("issuer_id", sa.UUID(), nullable=False),
        sa.Column("instrument_type", sa.String(30), nullable=False),
        sa.Column("share_class", sa.String(50), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name=op.f("ck_instruments_currency_code_format")),
        sa.CheckConstraint(
            "instrument_type IN ('common_share', 'preferred_share', 'unit', 'bdr', 'etf', 'fund', 'bond')",
            name=op.f("ck_instruments_instrument_type_values"),
        ),
        sa.ForeignKeyConstraint(
            ["issuer_id"], ["issuers.id"], name=op.f("fk_instruments_issuer_id_issuers"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_instruments")),
    )
    op.create_index(op.f("ix_instruments_issuer_id"), "instruments", ["issuer_id"])
    op.create_table(
        "issuer_aliases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("issuer_id", sa.UUID(), nullable=False),
        sa.Column("alias", sa.String(300), nullable=False),
        sa.Column("alias_normalized", sa.String(300), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name=op.f("ck_issuer_aliases_valid_window")),
        sa.ForeignKeyConstraint(
            ["issuer_id"], ["issuers.id"], name=op.f("fk_issuer_aliases_issuer_id_issuers"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_issuer_aliases")),
        sa.UniqueConstraint("issuer_id", "alias_normalized", "valid_from", name="uq_issuer_aliases_window_start"),
    )
    op.create_index(op.f("ix_issuer_aliases_alias_normalized"), "issuer_aliases", ["alias_normalized"])
    op.create_index(op.f("ix_issuer_aliases_issuer_id"), "issuer_aliases", ["issuer_id"])
    op.create_table(
        "listings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("instrument_id", sa.UUID(), nullable=False),
        sa.Column("exchange_code", sa.String(20), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("market_segment", sa.String(50), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name=op.f("ck_listings_valid_window")),
        postgresql.ExcludeConstraint(
            ("exchange_code", "="),
            ("ticker", "="),
            (sa.text("daterange(valid_from, valid_to, '[)')"), "&&"),
            name="ex_listings_ticker_window",
            using="gist",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name=op.f("fk_listings_instrument_id_instruments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_listings")),
    )
    op.create_index(op.f("ix_listings_instrument_id"), "listings", ["instrument_id"])
    op.create_table(
        "instrument_identifiers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("instrument_id", sa.UUID(), nullable=False),
        sa.Column("identifier_type", sa.String(30), nullable=False),
        sa.Column("identifier_value", sa.String(100), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name=op.f("ck_instrument_identifiers_valid_window")
        ),
        postgresql.ExcludeConstraint(
            ("identifier_type", "="),
            ("identifier_value", "="),
            (sa.text("daterange(valid_from, valid_to, '[)')"), "&&"),
            name="ex_instrument_identifiers_value_window",
            using="gist",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name=op.f("fk_instrument_identifiers_instrument_id_instruments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_instrument_identifiers")),
    )
    op.create_index(op.f("ix_instrument_identifiers_instrument_id"), "instrument_identifiers", ["instrument_id"])
    op.create_table(
        "peer_relationships",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("issuer_id", sa.UUID(), nullable=False),
        sa.Column("peer_issuer_id", sa.UUID(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.CheckConstraint("issuer_id <> peer_issuer_id", name=op.f("ck_peer_relationships_different_issuers")),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name=op.f("ck_peer_relationships_valid_window")
        ),
        sa.ForeignKeyConstraint(
            ["issuer_id"], ["issuers.id"], name=op.f("fk_peer_relationships_issuer_id_issuers"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["peer_issuer_id"],
            ["issuers.id"],
            name=op.f("fk_peer_relationships_peer_issuer_id_issuers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_peer_relationships")),
        sa.UniqueConstraint("issuer_id", "peer_issuer_id", "valid_from", name="uq_peer_relationships_window_start"),
    )
    op.create_index(op.f("ix_peer_relationships_issuer_id"), "peer_relationships", ["issuer_id"])
    op.create_index(op.f("ix_peer_relationships_peer_issuer_id"), "peer_relationships", ["peer_issuer_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_peer_relationships_peer_issuer_id"), table_name="peer_relationships")
    op.drop_index(op.f("ix_peer_relationships_issuer_id"), table_name="peer_relationships")
    op.drop_table("peer_relationships")
    op.drop_index(op.f("ix_instrument_identifiers_instrument_id"), table_name="instrument_identifiers")
    op.drop_table("instrument_identifiers")
    op.drop_index(op.f("ix_listings_instrument_id"), table_name="listings")
    op.drop_table("listings")
    op.drop_index(op.f("ix_issuer_aliases_issuer_id"), table_name="issuer_aliases")
    op.drop_index(op.f("ix_issuer_aliases_alias_normalized"), table_name="issuer_aliases")
    op.drop_table("issuer_aliases")
    op.drop_index(op.f("ix_instruments_issuer_id"), table_name="instruments")
    op.drop_table("instruments")
    op.drop_table("legal_entities")
