"""Range partitioning for financial_facts (quarterly by knowledge_at) and market_bars (monthly by bar_at).

Revision ID: 20260812_01
Revises: f7a100000011
Create Date: 2026-08-12

Strategy:
- financial_facts: partitioned by RANGE on knowledge_at (quarterly)
- market_bars: partitioned by RANGE on bar_at (monthly)
- Includes partition management functions for automated future partition creation
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260812_01"
down_revision: str | Sequence[str] | None = "f7a100000011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_financial_facts_partitioned() -> None:
    """Create the partitioned financial_facts table with quarterly partitions."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS financial_facts_partitioned (
            id                          UUID NOT NULL DEFAULT gen_random_uuid(),
            issuer_id                   UUID NOT NULL,
            reporting_period_id         UUID NOT NULL,
            statement_type              VARCHAR(20) NOT NULL,
            consolidation_scope         VARCHAR(20) NOT NULL,
            original_account_code       VARCHAR(100) NOT NULL,
            original_account_label      VARCHAR(500) NOT NULL,
            taxonomy_account_id         UUID,
            value                       NUMERIC(28, 8),
            currency_code               VARCHAR(3) NOT NULL,
            scale_factor                INTEGER NOT NULL,
            value_status                VARCHAR(20) NOT NULL,
            source_object_version_id    UUID NOT NULL,
            parser_version              VARCHAR(100) NOT NULL,
            mapping_rule_id             UUID,
            published_at                TIMESTAMPTZ NOT NULL,
            discovered_at               TIMESTAMPTZ NOT NULL,
            ingested_at                 TIMESTAMPTZ NOT NULL,
            validated_at                TIMESTAMPTZ NOT NULL,
            knowledge_at                TIMESTAMPTZ NOT NULL,
            valid_from                  TIMESTAMPTZ NOT NULL,
            valid_to                    TIMESTAMPTZ,
            revision_number             INTEGER NOT NULL,
            created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT pk_financial_facts PRIMARY KEY (id, knowledge_at),
            CONSTRAINT uq_financial_facts_business_revision
                UNIQUE (reporting_period_id, statement_type, consolidation_scope,
                        original_account_code, revision_number, knowledge_at),
            CONSTRAINT ck_financial_facts_value_status_values
                CHECK (value_status IN ('reported','calculated','missing',
                                        'not_applicable','parse_error','suppressed')),
            CONSTRAINT ck_financial_facts_value_matches_status
                CHECK (
                    ((value_status IN ('reported','calculated')) AND value IS NOT NULL) OR
                    ((value_status IN ('missing','not_applicable','parse_error','suppressed')) AND value IS NULL)
                ),
            CONSTRAINT ck_financial_facts_positive_scale CHECK (scale_factor > 0),
            CONSTRAINT ck_financial_facts_positive_revision CHECK (revision_number > 0),
            CONSTRAINT ck_financial_facts_valid_window CHECK (valid_to IS NULL OR valid_to > valid_from),
            CONSTRAINT ck_financial_facts_currency_code_format CHECK (currency_code ~ '^[A-Z]{3}$')
        ) PARTITION BY RANGE (knowledge_at)
        """
    )

    # Create quarterly partitions: current quarter + next 4 quarters
    op.execute(
        """
        DO $$
        DECLARE
            start_date DATE;
            end_date   DATE;
            q          INTEGER;
            part_name  TEXT;
        BEGIN
            FOR q IN 0..4 LOOP
                start_date := date_trunc('quarter', CURRENT_DATE) + (q || ' months')::interval;
                end_date   := start_date + INTERVAL '3 months';
                part_name  := 'financial_facts_y' || to_char(start_date, 'YYYY') || 'q' || to_char(start_date, 'Q');
                EXECUTE format(
                    'CREATE TABLE IF NOT EXISTS %I PARTITION OF financial_facts_partitioned
                     FOR VALUES FROM (%L) TO (%L)',
                    part_name, start_date, end_date
                );
            END LOOP;
        END $$;
        """
    )

    # Create indexes on the partitioned table (indexes propagate to partitions)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ffp_issuer_id ON financial_facts_partitioned (issuer_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ffp_reporting_period_id ON financial_facts_partitioned (reporting_period_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ffp_taxonomy_account_id ON financial_facts_partitioned (taxonomy_account_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ffp_source_object_version_id "
        "ON financial_facts_partitioned (source_object_version_id)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_ffp_knowledge_at ON financial_facts_partitioned (knowledge_at DESC)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ffp_issuer_knowledge_at "
        "ON financial_facts_partitioned (issuer_id, knowledge_at DESC)"
    )

    # FK constraints (must reference the original table names — parent tables exist)
    op.execute(
        """
        ALTER TABLE financial_facts_partitioned
            ADD CONSTRAINT fk_ffp_issuer_id
            FOREIGN KEY (issuer_id) REFERENCES issuers(id) ON DELETE CASCADE
        """
    )
    op.execute(
        """
        ALTER TABLE financial_facts_partitioned
            ADD CONSTRAINT fk_ffp_reporting_period_id
            FOREIGN KEY (reporting_period_id) REFERENCES reporting_periods(id) ON DELETE CASCADE
        """
    )
    op.execute(
        """
        ALTER TABLE financial_facts_partitioned
            ADD CONSTRAINT fk_ffp_taxonomy_account_id
            FOREIGN KEY (taxonomy_account_id) REFERENCES taxonomy_accounts(id) ON DELETE RESTRICT
        """
    )
    op.execute(
        """
        ALTER TABLE financial_facts_partitioned
            ADD CONSTRAINT fk_ffp_source_object_version_id
            FOREIGN KEY (source_object_version_id) REFERENCES source_object_versions(id) ON DELETE RESTRICT
        """
    )
    op.execute(
        """
        ALTER TABLE financial_facts_partitioned
            ADD CONSTRAINT fk_ffp_mapping_rule_id
            FOREIGN KEY (mapping_rule_id) REFERENCES account_mapping_rules(id) ON DELETE RESTRICT
        """
    )


def _create_market_bars_partitioned() -> None:
    """Create the partitioned market_bars table with monthly partitions."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS market_bars_partitioned (
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

            CONSTRAINT pk_market_bars PRIMARY KEY (id, bar_at),
            CONSTRAINT uq_market_bars_pit
                UNIQUE (listing_id, interval, bar_at, knowledge_at),
            CONSTRAINT ck_market_bars_valid_high_low CHECK (high_price >= low_price),
            CONSTRAINT ck_market_bars_nonnegative_volume CHECK (volume >= 0)
        ) PARTITION BY RANGE (bar_at)
        """
    )

    # Create monthly partitions: current month + next 6 months
    op.execute(
        """
        DO $$
        DECLARE
            start_date DATE;
            end_date   DATE;
            m          INTEGER;
            part_name  TEXT;
        BEGIN
            FOR m IN 0..6 LOOP
                start_date := date_trunc('month', CURRENT_DATE) + (m || ' months')::interval;
                end_date   := start_date + INTERVAL '1 month';
                part_name  := 'market_bars_y' || to_char(start_date, 'YYYY') || 'm' || to_char(start_date, 'MM');
                EXECUTE format(
                    'CREATE TABLE IF NOT EXISTS %I PARTITION OF market_bars_partitioned
                     FOR VALUES FROM (%L) TO (%L)',
                    part_name, start_date, end_date
                );
            END LOOP;
        END $$;
        """
    )

    # Create indexes
    op.execute("CREATE INDEX IF NOT EXISTS ix_mbp_listing_id ON market_bars_partitioned (listing_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_mbp_knowledge_at ON market_bars_partitioned (knowledge_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_mbp_listing_bar_at ON market_bars_partitioned (listing_id, bar_at DESC)")

    # FK constraints
    op.execute(
        """
        ALTER TABLE market_bars_partitioned
            ADD CONSTRAINT fk_mbp_listing_id
            FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
        """
    )
    op.execute(
        """
        ALTER TABLE market_bars_partitioned
            ADD CONSTRAINT fk_mbp_source_object_version_id
            FOREIGN KEY (source_object_version_id) REFERENCES source_object_versions(id) ON DELETE RESTRICT
        """
    )


def _migrate_data_financial_facts() -> None:
    """Copy data from financial_facts to financial_facts_partitioned."""
    op.execute(
        """
        INSERT INTO financial_facts_partitioned (
            id, issuer_id, reporting_period_id, statement_type, consolidation_scope,
            original_account_code, original_account_label, taxonomy_account_id,
            value, currency_code, scale_factor, value_status, source_object_version_id,
            parser_version, mapping_rule_id, published_at, discovered_at, ingested_at,
            validated_at, knowledge_at, valid_from, valid_to, revision_number,
            created_at, updated_at
        )
        SELECT
            id, issuer_id, reporting_period_id, statement_type, consolidation_scope,
            original_account_code, original_account_label, taxonomy_account_id,
            value, currency_code, scale_factor, value_status, source_object_version_id,
            parser_version, mapping_rule_id, published_at, discovered_at, ingested_at,
            validated_at, knowledge_at, valid_from, valid_to, revision_number,
            created_at, updated_at
        FROM financial_facts
        """
    )


def _migrate_data_market_bars() -> None:
    """Copy data from market_bars to market_bars_partitioned."""
    op.execute(
        """
        INSERT INTO market_bars_partitioned (
            id, listing_id, interval, bar_at, open_price, high_price,
            low_price, close_price, volume, source_object_version_id, knowledge_at
        )
        SELECT
            id, listing_id, interval, bar_at, open_price, high_price,
            low_price, close_price, volume, source_object_version_id, knowledge_at
        FROM market_bars
        """
    )


def _drop_original_tables() -> None:
    """Drop the original non-partitioned tables (handles dependent FKs)."""

    # Drop FKs that reference financial_facts (all tables with FKs to financial_facts.id)
    op.execute(
        "ALTER TABLE metric_fact_lineage "
        "DROP CONSTRAINT IF EXISTS "
        "fk_metric_fact_lineage_financial_fact_id_financial_facts"
    )
    op.execute(
        "ALTER TABLE restatement_logs DROP CONSTRAINT IF EXISTS fk_restatement_logs_superseded_fact_id_financial_facts"
    )
    op.execute("ALTER TABLE restatement_logs DROP CONSTRAINT IF EXISTS fk_restatement_logs_new_fact_id_financial_facts")
    op.execute(
        "ALTER TABLE valuation_assumptions "
        "DROP CONSTRAINT IF EXISTS "
        "fk_valuation_assumptions_financial_fact_id_financial_facts"
    )
    op.execute(
        "ALTER TABLE quality_incidents DROP CONSTRAINT IF EXISTS fk_quality_incidents_financial_fact_id_financial_facts"
    )

    # Drop indexes before dropping the tables
    op.execute("DROP INDEX IF EXISTS ix_financial_facts_issuer_knowledge_at")
    op.execute("DROP INDEX IF EXISTS ix_financial_facts_knowledge_at")
    op.execute("DROP INDEX IF EXISTS ix_financial_facts_source_object_version_id")
    op.execute("DROP INDEX IF EXISTS ix_financial_facts_taxonomy_account_id")
    op.execute("DROP INDEX IF EXISTS ix_financial_facts_reporting_period_id")
    op.execute("DROP INDEX IF EXISTS ix_financial_facts_issuer_id")

    op.execute("DROP INDEX IF EXISTS ix_market_bars_listing_bar_at")
    op.execute("DROP INDEX IF EXISTS ix_market_bars_knowledge_at")
    op.execute("DROP INDEX IF EXISTS ix_market_bars_listing_id")

    # Drop original tables
    op.execute("DROP TABLE IF EXISTS financial_facts CASCADE")
    op.execute("DROP TABLE IF EXISTS market_bars CASCADE")


def _rename_partitioned_tables() -> None:
    """Rename partitioned tables to original names."""
    op.execute("ALTER TABLE financial_facts_partitioned RENAME TO financial_facts")
    op.execute("ALTER TABLE market_bars_partitioned RENAME TO market_bars")

    # Rename constraints and indexes to original names
    op.execute("ALTER INDEX IF EXISTS pk_financial_facts RENAME TO pk_financial_facts")
    op.execute("ALTER TABLE financial_facts RENAME CONSTRAINT pk_financial_facts TO pk_financial_facts")
    op.execute(
        "ALTER TABLE financial_facts "
        "RENAME CONSTRAINT uq_financial_facts_business_revision "
        "TO uq_financial_facts_business_revision"
    )
    op.execute("ALTER TABLE financial_facts RENAME CONSTRAINT fk_ffp_issuer_id TO fk_financial_facts_issuer_id_issuers")
    op.execute(
        "ALTER TABLE financial_facts "
        "RENAME CONSTRAINT fk_ffp_reporting_period_id "
        "TO fk_financial_facts_reporting_period_id_reporting_periods"
    )
    op.execute(
        "ALTER TABLE financial_facts "
        "RENAME CONSTRAINT fk_ffp_taxonomy_account_id "
        "TO fk_financial_facts_taxonomy_account_id_taxonomy_accounts"
    )
    op.execute(
        "ALTER TABLE financial_facts "
        "RENAME CONSTRAINT fk_ffp_source_object_version_id "
        "TO fk_financial_facts_source_object_version_id_source_object_versions"
    )
    op.execute(
        "ALTER TABLE financial_facts "
        "RENAME CONSTRAINT fk_ffp_mapping_rule_id "
        "TO fk_financial_facts_mapping_rule_id_account_mapping_rules"
    )

    # Rename market_bars constraints
    op.execute("ALTER TABLE market_bars RENAME CONSTRAINT pk_market_bars TO pk_market_bars")
    op.execute("ALTER TABLE market_bars RENAME CONSTRAINT uq_market_bars_pit TO uq_market_bars_pit")
    op.execute("ALTER TABLE market_bars RENAME CONSTRAINT fk_mbp_listing_id TO fk_market_bars_listing_id_listings")
    op.execute(
        "ALTER TABLE market_bars "
        "RENAME CONSTRAINT fk_mbp_source_object_version_id "
        "TO fk_market_bars_source_object_version_id_source_object_versions"
    )

    # Rename indexes
    op.execute("ALTER INDEX IF EXISTS ix_ffp_issuer_id RENAME TO ix_financial_facts_issuer_id")
    op.execute("ALTER INDEX IF EXISTS ix_ffp_reporting_period_id RENAME TO ix_financial_facts_reporting_period_id")
    op.execute("ALTER INDEX IF EXISTS ix_ffp_taxonomy_account_id RENAME TO ix_financial_facts_taxonomy_account_id")
    op.execute(
        "ALTER INDEX IF EXISTS ix_ffp_source_object_version_id RENAME TO ix_financial_facts_source_object_version_id"
    )
    op.execute("ALTER INDEX IF EXISTS ix_ffp_knowledge_at RENAME TO ix_financial_facts_knowledge_at")
    op.execute("ALTER INDEX IF EXISTS ix_ffp_issuer_knowledge_at RENAME TO ix_financial_facts_issuer_knowledge_at")

    op.execute("ALTER INDEX IF EXISTS ix_mbp_listing_id RENAME TO ix_market_bars_listing_id")
    op.execute("ALTER INDEX IF EXISTS ix_mbp_knowledge_at RENAME TO ix_market_bars_knowledge_at")
    op.execute("ALTER INDEX IF EXISTS ix_mbp_listing_bar_at RENAME TO ix_market_bars_listing_bar_at")


def _restore_dependent_fks() -> None:
    """Restore FKs from dependent tables to the new partitioned financial_facts."""
    op.execute(
        """
        ALTER TABLE metric_fact_lineage
            ADD CONSTRAINT fk_metric_fact_lineage_financial_fact_id_financial_facts
            FOREIGN KEY (financial_fact_id) REFERENCES financial_facts(id, knowledge_at)
            ON DELETE RESTRICT
        """
    )
    op.execute(
        """
        ALTER TABLE restatement_logs
            ADD CONSTRAINT fk_restatement_logs_superseded_fact_id_financial_facts
            FOREIGN KEY (superseded_fact_id) REFERENCES financial_facts(id, knowledge_at)
            ON DELETE RESTRICT
        """
    )
    op.execute(
        """
        ALTER TABLE restatement_logs
            ADD CONSTRAINT fk_restatement_logs_new_fact_id_financial_facts
            FOREIGN KEY (new_fact_id) REFERENCES financial_facts(id, knowledge_at)
            ON DELETE RESTRICT
        """
    )
    op.execute(
        """
        ALTER TABLE valuation_assumptions
            ADD CONSTRAINT fk_valuation_assumptions_financial_fact_id_financial_facts
            FOREIGN KEY (financial_fact_id) REFERENCES financial_facts(id, knowledge_at)
            ON DELETE RESTRICT
        """
    )
    op.execute(
        """
        ALTER TABLE quality_incidents
            ADD CONSTRAINT fk_quality_incidents_financial_fact_id_financial_facts
            FOREIGN KEY (financial_fact_id) REFERENCES financial_facts(id, knowledge_at)
            ON DELETE SET NULL
        """
    )


def _create_partition_management_functions() -> None:
    """Create PL/pgSQL functions for automated partition management."""
    op.execute(
        """
        CREATE OR REPLACE FUNCTION create_financial_facts_partition(
            p_start_date DATE DEFAULT NULL
        ) RETURNS void AS $$
        DECLARE
            start_date DATE;
            end_date   DATE;
            part_name  TEXT;
        BEGIN
            start_date := COALESCE(p_start_date, date_trunc('quarter', CURRENT_DATE));
            end_date   := start_date + INTERVAL '3 months';
            part_name  := 'financial_facts_y' || to_char(start_date, 'YYYY') || 'q' || to_char(start_date, 'Q');

            IF NOT EXISTS (
                SELECT 1 FROM pg_class WHERE relname = part_name
            ) THEN
                EXECUTE format(
                    'CREATE TABLE %I PARTITION OF financial_facts FOR VALUES FROM (%L) TO (%L)',
                    part_name, start_date, end_date
                );
                RAISE NOTICE 'Created partition: %', part_name;
            ELSE
                RAISE NOTICE 'Partition already exists: %', part_name;
            END IF;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION create_market_bars_partition(
            p_start_date DATE DEFAULT NULL
        ) RETURNS void AS $$
        DECLARE
            start_date DATE;
            end_date   DATE;
            part_name  TEXT;
        BEGIN
            start_date := COALESCE(p_start_date, date_trunc('month', CURRENT_DATE));
            end_date   := start_date + INTERVAL '1 month';
            part_name  := 'market_bars_y' || to_char(start_date, 'YYYY') || 'm' || to_char(start_date, 'MM');

            IF NOT EXISTS (
                SELECT 1 FROM pg_class WHERE relname = part_name
            ) THEN
                EXECUTE format(
                    'CREATE TABLE %I PARTITION OF market_bars FOR VALUES FROM (%L) TO (%L)',
                    part_name, start_date, end_date
                );
                RAISE NOTICE 'Created partition: %', part_name;
            ELSE
                RAISE NOTICE 'Partition already exists: %', part_name;
            END IF;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # Convenience function to ensure next N partitions exist
    op.execute(
        """
        CREATE OR REPLACE FUNCTION ensure_future_partitions() RETURNS void AS $$
        DECLARE
            i INTEGER;
        BEGIN
            -- Ensure 4 future quarterly partitions for financial_facts
            FOR i IN 0..4 LOOP
                PERFORM create_financial_facts_partition(
                    date_trunc('quarter', CURRENT_DATE) + (i || ' months')::interval
                );
            END LOOP;

            -- Ensure 6 future monthly partitions for market_bars
            FOR i IN 0..6 LOOP
                PERFORM create_market_bars_partition(
                    date_trunc('month', CURRENT_DATE) + (i || ' months')::interval
                );
            END LOOP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # 1. Create partitioned tables
    _create_financial_facts_partitioned()
    _create_market_bars_partitioned()

    # 2. Migrate data
    _migrate_data_financial_facts()
    _migrate_data_market_bars()

    # 3. Drop original tables (and dependent FKs/indexes)
    _drop_original_tables()

    # 4. Rename partitioned tables to original names
    _rename_partitioned_tables()

    # 5. Restore FKs from dependent tables
    _restore_dependent_fks()

    # 6. Create partition management functions
    _create_partition_management_functions()


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    # Drop partition management functions
    op.execute("DROP FUNCTION IF EXISTS ensure_future_partitions()")
    op.execute("DROP FUNCTION IF EXISTS create_market_bars_partition(DATE)")
    op.execute("DROP FUNCTION IF EXISTS create_financial_facts_partition(DATE)")

    # Drop dependent FKs
    op.execute("ALTER TABLE restatement_logs DROP CONSTRAINT IF EXISTS fk_restatement_logs_new_fact_id_financial_facts")
    op.execute(
        "ALTER TABLE restatement_logs DROP CONSTRAINT IF EXISTS fk_restatement_logs_superseded_fact_id_financial_facts"
    )
    op.execute(
        "ALTER TABLE metric_fact_lineage "
        "DROP CONSTRAINT IF EXISTS "
        "fk_metric_fact_lineage_financial_fact_id_financial_facts"
    )
    op.execute(
        "ALTER TABLE valuation_assumptions "
        "DROP CONSTRAINT IF EXISTS "
        "fk_valuation_assumptions_financial_fact_id_financial_facts"
    )
    op.execute(
        "ALTER TABLE quality_incidents DROP CONSTRAINT IF EXISTS fk_quality_incidents_financial_fact_id_financial_facts"
    )

    # Rename constraints and indexes back to temporary names
    op.execute("ALTER INDEX IF EXISTS ix_financial_facts_issuer_id RENAME TO ix_ffp_issuer_id")
    op.execute("ALTER INDEX IF EXISTS ix_financial_facts_reporting_period_id RENAME TO ix_ffp_reporting_period_id")
    op.execute("ALTER INDEX IF EXISTS ix_financial_facts_taxonomy_account_id RENAME TO ix_ffp_taxonomy_account_id")
    op.execute(
        "ALTER INDEX IF EXISTS ix_financial_facts_source_object_version_id RENAME TO ix_ffp_source_object_version_id"
    )
    op.execute("ALTER INDEX IF EXISTS ix_financial_facts_knowledge_at RENAME TO ix_ffp_knowledge_at")
    op.execute("ALTER INDEX IF EXISTS ix_financial_facts_issuer_knowledge_at RENAME TO ix_ffp_issuer_knowledge_at")

    op.execute("ALTER INDEX IF EXISTS ix_market_bars_listing_id RENAME TO ix_mbp_listing_id")
    op.execute("ALTER INDEX IF EXISTS ix_market_bars_knowledge_at RENAME TO ix_mbp_knowledge_at")
    op.execute("ALTER INDEX IF EXISTS ix_market_bars_listing_bar_at RENAME TO ix_mbp_listing_bar_at")

    op.execute("ALTER TABLE financial_facts RENAME CONSTRAINT fk_ffp_issuer_id TO fk_financial_facts_issuer_id_issuers")
    op.execute(
        "ALTER TABLE financial_facts "
        "RENAME CONSTRAINT fk_ffp_reporting_period_id "
        "TO fk_financial_facts_reporting_period_id_reporting_periods"
    )
    op.execute(
        "ALTER TABLE financial_facts "
        "RENAME CONSTRAINT fk_ffp_taxonomy_account_id "
        "TO fk_financial_facts_taxonomy_account_id_taxonomy_accounts"
    )
    op.execute(
        "ALTER TABLE financial_facts "
        "RENAME CONSTRAINT fk_ffp_source_object_version_id "
        "TO fk_financial_facts_source_object_version_id_source_object_versions"
    )
    op.execute(
        "ALTER TABLE financial_facts "
        "RENAME CONSTRAINT fk_ffp_mapping_rule_id "
        "TO fk_financial_facts_mapping_rule_id_account_mapping_rules"
    )

    op.execute("ALTER TABLE market_bars RENAME CONSTRAINT fk_mbp_listing_id TO fk_market_bars_listing_id_listings")
    op.execute(
        "ALTER TABLE market_bars "
        "RENAME CONSTRAINT fk_mbp_source_object_version_id "
        "TO fk_market_bars_source_object_version_id_source_object_versions"
    )

    # Rename tables back to temporary names
    op.execute("ALTER TABLE financial_facts RENAME TO financial_facts_partitioned")
    op.execute("ALTER TABLE market_bars RENAME TO market_bars_partitioned")

    # Drop partitioned tables (cascades to partitions)
    op.execute("DROP TABLE IF EXISTS financial_facts_partitioned CASCADE")
    op.execute("DROP TABLE IF EXISTS market_bars_partitioned CASCADE")

    # Recreate original non-partitioned financial_facts
    op.execute(
        """
        CREATE TABLE financial_facts (
            id                          UUID NOT NULL DEFAULT gen_random_uuid(),
            issuer_id                   UUID NOT NULL,
            reporting_period_id         UUID NOT NULL,
            statement_type              VARCHAR(20) NOT NULL,
            consolidation_scope         VARCHAR(20) NOT NULL,
            original_account_code       VARCHAR(100) NOT NULL,
            original_account_label      VARCHAR(500) NOT NULL,
            taxonomy_account_id         UUID,
            value                       NUMERIC(28, 8),
            currency_code               VARCHAR(3) NOT NULL,
            scale_factor                INTEGER NOT NULL,
            value_status                VARCHAR(20) NOT NULL,
            source_object_version_id    UUID NOT NULL,
            parser_version              VARCHAR(100) NOT NULL,
            mapping_rule_id             UUID,
            published_at                TIMESTAMPTZ NOT NULL,
            discovered_at               TIMESTAMPTZ NOT NULL,
            ingested_at                 TIMESTAMPTZ NOT NULL,
            validated_at                TIMESTAMPTZ NOT NULL,
            knowledge_at                TIMESTAMPTZ NOT NULL,
            valid_from                  TIMESTAMPTZ NOT NULL,
            valid_to                    TIMESTAMPTZ,
            revision_number             INTEGER NOT NULL,
            created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT pk_financial_facts PRIMARY KEY (id),
            CONSTRAINT uq_financial_facts_business_revision
                UNIQUE (reporting_period_id, statement_type, consolidation_scope,
                        original_account_code, revision_number),
            CONSTRAINT ck_financial_facts_value_status_values
                CHECK (value_status IN ('reported','calculated','missing',
                                        'not_applicable','parse_error','suppressed')),
            CONSTRAINT ck_financial_facts_value_matches_status
                CHECK (
                    ((value_status IN ('reported','calculated')) AND value IS NOT NULL) OR
                    ((value_status IN ('missing','not_applicable','parse_error','suppressed')) AND value IS NULL)
                ),
            CONSTRAINT ck_financial_facts_positive_scale CHECK (scale_factor > 0),
            CONSTRAINT ck_financial_facts_positive_revision CHECK (revision_number > 0),
            CONSTRAINT ck_financial_facts_valid_window CHECK (valid_to IS NULL OR valid_to > valid_from),
            CONSTRAINT ck_financial_facts_currency_code_format CHECK (currency_code ~ '^[A-Z]{3}$')
        )
        """
    )
    op.execute("CREATE INDEX ix_financial_facts_issuer_id ON financial_facts (issuer_id)")
    op.execute("CREATE INDEX ix_financial_facts_reporting_period_id ON financial_facts (reporting_period_id)")
    op.execute("CREATE INDEX ix_financial_facts_taxonomy_account_id ON financial_facts (taxonomy_account_id)")
    op.execute("CREATE INDEX ix_financial_facts_source_object_version_id ON financial_facts (source_object_version_id)")
    op.execute("CREATE INDEX ix_financial_facts_knowledge_at ON financial_facts (knowledge_at)")
    op.execute("CREATE INDEX ix_financial_facts_issuer_knowledge_at ON financial_facts (issuer_id, knowledge_at DESC)")
    op.execute(
        "ALTER TABLE financial_facts ADD CONSTRAINT fk_financial_facts_issuer_id_issuers "
        "FOREIGN KEY (issuer_id) REFERENCES issuers(id) ON DELETE CASCADE"
    )
    op.execute(
        "ALTER TABLE financial_facts ADD CONSTRAINT fk_financial_facts_reporting_period_id_reporting_periods "
        "FOREIGN KEY (reporting_period_id) REFERENCES reporting_periods(id) ON DELETE CASCADE"
    )
    op.execute(
        "ALTER TABLE financial_facts ADD CONSTRAINT fk_financial_facts_taxonomy_account_id_taxonomy_accounts "
        "FOREIGN KEY (taxonomy_account_id) REFERENCES taxonomy_accounts(id) ON DELETE RESTRICT"
    )
    op.execute(
        "ALTER TABLE financial_facts ADD CONSTRAINT fk_financial_facts_source_object_version_id_source_object_versions "
        "FOREIGN KEY (source_object_version_id) REFERENCES source_object_versions(id) ON DELETE RESTRICT"
    )
    op.execute(
        "ALTER TABLE financial_facts ADD CONSTRAINT fk_financial_facts_mapping_rule_id_account_mapping_rules "
        "FOREIGN KEY (mapping_rule_id) REFERENCES account_mapping_rules(id) ON DELETE RESTRICT"
    )

    # Recreate original non-partitioned market_bars
    op.execute(
        """
        CREATE TABLE market_bars (
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

            CONSTRAINT pk_market_bars PRIMARY KEY (id),
            CONSTRAINT uq_market_bars_pit
                UNIQUE (listing_id, interval, bar_at, knowledge_at),
            CONSTRAINT ck_market_bars_valid_high_low CHECK (high_price >= low_price),
            CONSTRAINT ck_market_bars_nonnegative_volume CHECK (volume >= 0)
        )
        """
    )
    op.execute("CREATE INDEX ix_market_bars_listing_id ON market_bars (listing_id)")
    op.execute("CREATE INDEX ix_market_bars_knowledge_at ON market_bars (knowledge_at)")
    op.execute("CREATE INDEX ix_market_bars_listing_bar_at ON market_bars (listing_id, bar_at DESC)")
    op.execute(
        "ALTER TABLE market_bars ADD CONSTRAINT fk_market_bars_listing_id_listings "
        "FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE"
    )
    op.execute(
        "ALTER TABLE market_bars ADD CONSTRAINT fk_market_bars_source_object_version_id_source_object_versions "
        "FOREIGN KEY (source_object_version_id) REFERENCES source_object_versions(id) ON DELETE RESTRICT"
    )

    # Restore dependent FKs
    op.execute(
        "ALTER TABLE metric_fact_lineage "
        "ADD CONSTRAINT fk_metric_fact_lineage_financial_fact_id_financial_facts "
        "FOREIGN KEY (financial_fact_id) REFERENCES financial_facts(id) ON DELETE RESTRICT"
    )
    op.execute(
        "ALTER TABLE restatement_logs "
        "ADD CONSTRAINT fk_restatement_logs_superseded_fact_id_financial_facts "
        "FOREIGN KEY (superseded_fact_id) REFERENCES financial_facts(id) ON DELETE RESTRICT"
    )
    op.execute(
        "ALTER TABLE restatement_logs "
        "ADD CONSTRAINT fk_restatement_logs_new_fact_id_financial_facts "
        "FOREIGN KEY (new_fact_id) REFERENCES financial_facts(id) ON DELETE RESTRICT"
    )
    op.execute(
        "ALTER TABLE valuation_assumptions "
        "ADD CONSTRAINT fk_valuation_assumptions_financial_fact_id_financial_facts "
        "FOREIGN KEY (financial_fact_id) REFERENCES financial_facts(id) ON DELETE RESTRICT"
    )
    op.execute(
        "ALTER TABLE quality_incidents "
        "ADD CONSTRAINT fk_quality_incidents_financial_fact_id_financial_facts "
        "FOREIGN KEY (financial_fact_id) REFERENCES financial_facts(id) ON DELETE SET NULL"
    )
