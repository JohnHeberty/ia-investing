"""point-in-time financial facts and metric lineage

Revision ID: a2f100000003
Revises: a2f100000002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a2f100000003"
down_revision: str | Sequence[str] | None = "a2f100000002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metric_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("formula", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("frequency", sa.String(30), nullable=False),
        sa.Column("dependencies", sa.JSON(), nullable=False),
        sa.CheckConstraint("version > 0", name=op.f("ck_metric_definitions_positive_version")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_metric_definitions")),
        sa.UniqueConstraint("name", "version", name="uq_metric_definitions_name_version"),
    )
    op.create_table(
        "reporting_periods",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("issuer_id", sa.UUID(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("period_type", sa.String(20), nullable=False),
        sa.Column("consolidation_scope", sa.String(20), nullable=False),
        sa.CheckConstraint(
            "consolidation_scope IN ('individual', 'consolidated')", name=op.f("ck_reporting_periods_scope_values")
        ),
        sa.CheckConstraint("period_end >= period_start", name=op.f("ck_reporting_periods_valid_dates")),
        sa.CheckConstraint(
            "period_type IN ('annual', 'quarterly', 'year_to_date')",
            name=op.f("ck_reporting_periods_period_type_values"),
        ),
        sa.ForeignKeyConstraint(
            ["issuer_id"], ["issuers.id"], name=op.f("fk_reporting_periods_issuer_id_issuers"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reporting_periods")),
        sa.UniqueConstraint(
            "issuer_id",
            "period_start",
            "period_end",
            "period_type",
            "consolidation_scope",
            name="uq_reporting_periods_business_key",
        ),
    )
    op.create_index(op.f("ix_reporting_periods_issuer_id"), "reporting_periods", ["issuer_id"])
    op.create_table(
        "taxonomy_accounts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("taxonomy_version", sa.String(50), nullable=False),
        sa.Column("canonical_code", sa.String(100), nullable=False),
        sa.Column("name_pt", sa.String(300), nullable=False),
        sa.Column("statement_type", sa.String(20), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("normal_balance", sa.String(10), nullable=True),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["taxonomy_accounts.id"],
            name=op.f("fk_taxonomy_accounts_parent_id_taxonomy_accounts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_taxonomy_accounts")),
        sa.UniqueConstraint("taxonomy_version", "canonical_code", name="uq_taxonomy_accounts_version_code"),
    )
    op.create_table(
        "account_mapping_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("rule_set", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("source_statement_type", sa.String(20), nullable=False),
        sa.Column("source_code_pattern", sa.String(300), nullable=False),
        sa.Column("issuer_id", sa.UUID(), nullable=True),
        sa.Column("taxonomy_account_id", sa.UUID(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("priority >= 0", name=op.f("ck_account_mapping_rules_nonnegative_priority")),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name=op.f("ck_account_mapping_rules_valid_window"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_account_mapping_rules_positive_version")),
        sa.ForeignKeyConstraint(
            ["issuer_id"], ["issuers.id"], name=op.f("fk_account_mapping_rules_issuer_id_issuers"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["taxonomy_account_id"],
            ["taxonomy_accounts.id"],
            name=op.f("fk_account_mapping_rules_taxonomy_account_id_taxonomy_accounts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_mapping_rules")),
        sa.UniqueConstraint("rule_set", "version", "priority", name="uq_account_mapping_rules_priority"),
    )
    op.create_table(
        "financial_facts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("issuer_id", sa.UUID(), nullable=False),
        sa.Column("reporting_period_id", sa.UUID(), nullable=False),
        sa.Column("statement_type", sa.String(20), nullable=False),
        sa.Column("consolidation_scope", sa.String(20), nullable=False),
        sa.Column("original_account_code", sa.String(100), nullable=False),
        sa.Column("original_account_label", sa.String(500), nullable=False),
        sa.Column("taxonomy_account_id", sa.UUID(), nullable=True),
        sa.Column("value", sa.Numeric(28, 8), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("scale_factor", sa.Integer(), nullable=False),
        sa.Column("value_status", sa.String(20), nullable=False),
        sa.Column("source_object_version_id", sa.UUID(), nullable=False),
        sa.Column("parser_version", sa.String(100), nullable=False),
        sa.Column("mapping_rule_id", sa.UUID(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("knowledge_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name=op.f("ck_financial_facts_currency_code_format")),
        sa.CheckConstraint("revision_number > 0", name=op.f("ck_financial_facts_positive_revision")),
        sa.CheckConstraint("scale_factor > 0", name=op.f("ck_financial_facts_positive_scale")),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name=op.f("ck_financial_facts_valid_window")),
        sa.CheckConstraint(
            "((value_status IN ('reported', 'calculated')) AND value IS NOT NULL) OR "
            "((value_status IN ('missing', 'not_applicable', 'parse_error', 'suppressed')) AND value IS NULL)",
            name=op.f("ck_financial_facts_value_matches_status"),
        ),
        sa.CheckConstraint(
            "value_status IN ('reported', 'calculated', 'missing', 'not_applicable', 'parse_error', 'suppressed')",
            name=op.f("ck_financial_facts_value_status_values"),
        ),
        sa.ForeignKeyConstraint(
            ["issuer_id"], ["issuers.id"], name=op.f("fk_financial_facts_issuer_id_issuers"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["mapping_rule_id"],
            ["account_mapping_rules.id"],
            name=op.f("fk_financial_facts_mapping_rule_id_account_mapping_rules"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reporting_period_id"],
            ["reporting_periods.id"],
            name=op.f("fk_financial_facts_reporting_period_id_reporting_periods"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_object_version_id"],
            ["source_object_versions.id"],
            name=op.f("fk_financial_facts_source_object_version_id_source_object_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["taxonomy_account_id"],
            ["taxonomy_accounts.id"],
            name=op.f("fk_financial_facts_taxonomy_account_id_taxonomy_accounts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_financial_facts")),
        sa.UniqueConstraint(
            "reporting_period_id",
            "statement_type",
            "consolidation_scope",
            "original_account_code",
            "revision_number",
            name="uq_financial_facts_business_revision",
        ),
    )
    fact_indexes = (
        "issuer_id",
        "reporting_period_id",
        "taxonomy_account_id",
        "source_object_version_id",
        "knowledge_at",
    )
    for column in fact_indexes:
        op.create_index(op.f(f"ix_financial_facts_{column}"), "financial_facts", [column])
    op.create_table(
        "metric_observations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("issuer_id", sa.UUID(), nullable=False),
        sa.Column("reporting_period_id", sa.UUID(), nullable=False),
        sa.Column("metric_definition_id", sa.UUID(), nullable=False),
        sa.Column("value", sa.Numeric(28, 10), nullable=True),
        sa.Column("value_status", sa.String(20), nullable=False),
        sa.Column("quality_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("coverage_ratio", sa.Numeric(5, 4), nullable=False),
        sa.Column("data_as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calculation_version", sa.String(100), nullable=False),
        sa.CheckConstraint("coverage_ratio BETWEEN 0 AND 1", name=op.f("ck_metric_observations_coverage_range")),
        sa.CheckConstraint("quality_score BETWEEN 0 AND 1", name=op.f("ck_metric_observations_quality_range")),
        sa.ForeignKeyConstraint(
            ["issuer_id"], ["issuers.id"], name=op.f("fk_metric_observations_issuer_id_issuers"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["metric_definition_id"],
            ["metric_definitions.id"],
            name=op.f("fk_metric_observations_metric_definition_id_metric_definitions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reporting_period_id"],
            ["reporting_periods.id"],
            name=op.f("fk_metric_observations_reporting_period_id_reporting_periods"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_metric_observations")),
        sa.UniqueConstraint(
            "issuer_id",
            "reporting_period_id",
            "metric_definition_id",
            "data_as_of",
            name="uq_metric_observations_as_of",
        ),
    )
    op.create_index(op.f("ix_metric_observations_data_as_of"), "metric_observations", ["data_as_of"])
    op.create_index(op.f("ix_metric_observations_issuer_id"), "metric_observations", ["issuer_id"])
    op.create_table(
        "metric_fact_lineage",
        sa.Column("metric_observation_id", sa.UUID(), nullable=False),
        sa.Column("financial_fact_id", sa.UUID(), nullable=False),
        sa.Column("input_role", sa.String(100), nullable=False),
        sa.ForeignKeyConstraint(
            ["financial_fact_id"],
            ["financial_facts.id"],
            name=op.f("fk_metric_fact_lineage_financial_fact_id_financial_facts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["metric_observation_id"],
            ["metric_observations.id"],
            name=op.f("fk_metric_fact_lineage_metric_observation_id_metric_observations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("metric_observation_id", "financial_fact_id", name=op.f("pk_metric_fact_lineage")),
    )


def downgrade() -> None:
    op.drop_table("metric_fact_lineage")
    op.drop_index(op.f("ix_metric_observations_issuer_id"), table_name="metric_observations")
    op.drop_index(op.f("ix_metric_observations_data_as_of"), table_name="metric_observations")
    op.drop_table("metric_observations")
    fact_indexes = (
        "knowledge_at",
        "source_object_version_id",
        "taxonomy_account_id",
        "reporting_period_id",
        "issuer_id",
    )
    for column in fact_indexes:
        op.drop_index(op.f(f"ix_financial_facts_{column}"), table_name="financial_facts")
    op.drop_table("financial_facts")
    op.drop_table("account_mapping_rules")
    op.drop_table("taxonomy_accounts")
    op.drop_index(op.f("ix_reporting_periods_issuer_id"), table_name="reporting_periods")
    op.drop_table("reporting_periods")
    op.drop_table("metric_definitions")
