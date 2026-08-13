"""Range-partition market bars by month.

Revision ID: 20260812_01
Revises: f7a100000011
Create Date: 2026-08-12

``financial_facts`` deliberately remains non-partitioned. PostgreSQL requires every
unique/primary key on a range-partitioned table to contain the partition key. The
table is referenced by several one-column foreign keys and also has a business
unique key that does not contain ``knowledge_at``. Partitioning it without changing
those public keys would silently remove relational guarantees or make the migration
impossible to apply.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260812_01"
down_revision: str | Sequence[str] | None = "f7a100000011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_partitioned_table() -> None:
    # Temporary constraint names are required because PostgreSQL constraint-backed
    # indexes share the schema namespace with the constraints on the source table.
    op.execute(
        """
        CREATE TABLE market_bars_partitioned (
            id                       UUID NOT NULL DEFAULT gen_random_uuid(),
            listing_id               UUID NOT NULL,
            interval                 VARCHAR(10) NOT NULL,
            bar_at                   TIMESTAMPTZ NOT NULL,
            open_price               NUMERIC(20, 8) NOT NULL,
            high_price               NUMERIC(20, 8) NOT NULL,
            low_price                NUMERIC(20, 8) NOT NULL,
            close_price              NUMERIC(20, 8) NOT NULL,
            volume                   INTEGER NOT NULL,
            source_object_version_id UUID NOT NULL,
            knowledge_at             TIMESTAMPTZ NOT NULL,

            CONSTRAINT pk_market_bars_partitioned PRIMARY KEY (id, bar_at),
            CONSTRAINT uq_market_bars_partitioned_pit
                UNIQUE (listing_id, interval, bar_at, knowledge_at),
            CONSTRAINT ck_market_bars_partitioned_valid_high_low CHECK (high_price >= low_price),
            CONSTRAINT ck_market_bars_partitioned_nonnegative_volume CHECK (volume >= 0),
            CONSTRAINT fk_mbp_listing_id
                FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE,
            CONSTRAINT fk_mbp_source_object_version_id
                FOREIGN KEY (source_object_version_id) REFERENCES source_object_versions(id) ON DELETE RESTRICT
        ) PARTITION BY RANGE (bar_at)
        """
    )

    # Cover all existing data plus the next six months. This avoids a DEFAULT
    # partition whose rows would later prevent creation of an overlapping month.
    op.execute(
        """
        DO $$
        DECLARE
            month_start DATE;
            final_month DATE := date_trunc('month', CURRENT_DATE) + INTERVAL '6 months';
            part_name TEXT;
        BEGIN
            SELECT COALESCE(date_trunc('month', min(bar_at)), date_trunc('month', CURRENT_DATE))::date
              INTO month_start
              FROM market_bars;

            WHILE month_start <= final_month LOOP
                part_name := 'market_bars_y' || to_char(month_start, 'YYYY') || 'm' || to_char(month_start, 'MM');
                EXECUTE format(
                    'CREATE TABLE %I PARTITION OF market_bars_partitioned FOR VALUES FROM (%L) TO (%L)',
                    part_name, month_start, month_start + INTERVAL '1 month'
                );
                month_start := month_start + INTERVAL '1 month';
            END LOOP;
        END $$
        """
    )

    op.execute("CREATE INDEX ix_mbp_listing_id ON market_bars_partitioned (listing_id)")
    op.execute("CREATE INDEX ix_mbp_knowledge_at ON market_bars_partitioned (knowledge_at)")
    op.execute("CREATE INDEX ix_mbp_listing_bar_at ON market_bars_partitioned (listing_id, bar_at DESC)")


def _create_partition_functions() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION create_market_bars_partition(
            p_start_date DATE DEFAULT NULL
        ) RETURNS void AS $$
        DECLARE
            start_date DATE := date_trunc('month', COALESCE(p_start_date, CURRENT_DATE));
            part_name TEXT;
        BEGIN
            part_name := 'market_bars_y' || to_char(start_date, 'YYYY') || 'm' || to_char(start_date, 'MM');
            IF to_regclass(part_name) IS NULL THEN
                EXECUTE format(
                    'CREATE TABLE %I PARTITION OF market_bars FOR VALUES FROM (%L) TO (%L)',
                    part_name, start_date, start_date + INTERVAL '1 month'
                );
            END IF;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION ensure_future_partitions() RETURNS void AS $$
        DECLARE
            month_offset INTEGER;
        BEGIN
            FOR month_offset IN 0..6 LOOP
                PERFORM create_market_bars_partition(
                    (date_trunc('month', CURRENT_DATE) + (month_offset || ' months')::interval)::date
                );
            END LOOP;
        END;
        $$ LANGUAGE plpgsql
        """
    )


def upgrade() -> None:
    _create_partitioned_table()
    op.execute(
        """
        INSERT INTO market_bars_partitioned (
            id, listing_id, interval, bar_at, open_price, high_price,
            low_price, close_price, volume, source_object_version_id, knowledge_at
        )
        SELECT id, listing_id, interval, bar_at, open_price, high_price,
               low_price, close_price, volume, source_object_version_id, knowledge_at
          FROM market_bars
        """
    )

    op.execute("DROP TABLE market_bars")
    op.execute("ALTER TABLE market_bars_partitioned RENAME TO market_bars")
    op.execute("ALTER TABLE market_bars RENAME CONSTRAINT pk_market_bars_partitioned TO pk_market_bars")
    op.execute("ALTER TABLE market_bars RENAME CONSTRAINT uq_market_bars_partitioned_pit TO uq_market_bars_pit")
    op.execute(
        "ALTER TABLE market_bars RENAME CONSTRAINT "
        "ck_market_bars_partitioned_valid_high_low TO ck_market_bars_valid_high_low"
    )
    op.execute(
        "ALTER TABLE market_bars RENAME CONSTRAINT "
        "ck_market_bars_partitioned_nonnegative_volume TO ck_market_bars_nonnegative_volume"
    )
    op.execute("ALTER TABLE market_bars RENAME CONSTRAINT fk_mbp_listing_id TO fk_market_bars_listing_id_listings")
    op.execute(
        "ALTER TABLE market_bars RENAME CONSTRAINT fk_mbp_source_object_version_id "
        "TO fk_market_bars_source_object_version_id_source_object_versions"
    )
    op.execute("ALTER INDEX ix_mbp_listing_id RENAME TO ix_market_bars_listing_id")
    op.execute("ALTER INDEX ix_mbp_knowledge_at RENAME TO ix_market_bars_knowledge_at")
    op.execute("ALTER INDEX ix_mbp_listing_bar_at RENAME TO ix_market_bars_listing_bar_at")
    _create_partition_functions()


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS ensure_future_partitions()")
    op.execute("DROP FUNCTION IF EXISTS create_market_bars_partition(DATE)")
    op.execute(
        """
        CREATE TABLE market_bars_unpartitioned (
            id                       UUID NOT NULL DEFAULT gen_random_uuid(),
            listing_id               UUID NOT NULL,
            interval                 VARCHAR(10) NOT NULL,
            bar_at                   TIMESTAMPTZ NOT NULL,
            open_price               NUMERIC(20, 8) NOT NULL,
            high_price               NUMERIC(20, 8) NOT NULL,
            low_price                NUMERIC(20, 8) NOT NULL,
            close_price              NUMERIC(20, 8) NOT NULL,
            volume                   INTEGER NOT NULL,
            source_object_version_id UUID NOT NULL,
            knowledge_at             TIMESTAMPTZ NOT NULL,
            CONSTRAINT pk_market_bars_unpartitioned PRIMARY KEY (id),
            CONSTRAINT uq_market_bars_unpartitioned_pit UNIQUE (listing_id, interval, bar_at, knowledge_at),
            CONSTRAINT ck_market_bars_unpartitioned_valid_high_low CHECK (high_price >= low_price),
            CONSTRAINT ck_market_bars_unpartitioned_nonnegative_volume CHECK (volume >= 0),
            CONSTRAINT fk_mbu_listing_id FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE,
            CONSTRAINT fk_mbu_source_object_version_id FOREIGN KEY (source_object_version_id)
                REFERENCES source_object_versions(id) ON DELETE RESTRICT
        )
        """
    )
    op.execute(
        """
        INSERT INTO market_bars_unpartitioned
        SELECT id, listing_id, interval, bar_at, open_price, high_price,
               low_price, close_price, volume, source_object_version_id, knowledge_at
          FROM market_bars
        """
    )
    op.execute("DROP TABLE market_bars")
    op.execute("ALTER TABLE market_bars_unpartitioned RENAME TO market_bars")
    op.execute("ALTER TABLE market_bars RENAME CONSTRAINT pk_market_bars_unpartitioned TO pk_market_bars")
    op.execute("ALTER TABLE market_bars RENAME CONSTRAINT uq_market_bars_unpartitioned_pit TO uq_market_bars_pit")
    op.execute(
        "ALTER TABLE market_bars RENAME CONSTRAINT "
        "ck_market_bars_unpartitioned_valid_high_low TO ck_market_bars_valid_high_low"
    )
    op.execute(
        "ALTER TABLE market_bars RENAME CONSTRAINT "
        "ck_market_bars_unpartitioned_nonnegative_volume TO ck_market_bars_nonnegative_volume"
    )
    op.execute("ALTER TABLE market_bars RENAME CONSTRAINT fk_mbu_listing_id TO fk_market_bars_listing_id_listings")
    op.execute(
        "ALTER TABLE market_bars RENAME CONSTRAINT fk_mbu_source_object_version_id "
        "TO fk_market_bars_source_object_version_id_source_object_versions"
    )
    op.execute("CREATE INDEX ix_market_bars_listing_id ON market_bars (listing_id)")
    op.execute("CREATE INDEX ix_market_bars_knowledge_at ON market_bars (knowledge_at)")
    op.execute("CREATE INDEX ix_market_bars_listing_bar_at ON market_bars (listing_id, bar_at DESC)")
