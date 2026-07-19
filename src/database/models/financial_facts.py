from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class ReportingPeriod(Base):
    __tablename__ = "reporting_periods"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    issuer_id: Mapped[UUID] = mapped_column(sa.ForeignKey("issuers.id", ondelete="CASCADE"), index=True)
    period_start: Mapped[date]
    period_end: Mapped[date]
    fiscal_year: Mapped[int]
    period_type: Mapped[str] = mapped_column(sa.String(20))
    consolidation_scope: Mapped[str] = mapped_column(sa.String(20))

    __table_args__ = (
        sa.UniqueConstraint(
            "issuer_id",
            "period_start",
            "period_end",
            "period_type",
            "consolidation_scope",
            name="uq_reporting_periods_business_key",
        ),
        sa.CheckConstraint("period_end >= period_start", name="valid_dates"),
        sa.CheckConstraint("period_type IN ('annual', 'quarterly', 'year_to_date')", name="period_type_values"),
        sa.CheckConstraint("consolidation_scope IN ('individual', 'consolidated')", name="scope_values"),
    )


class TaxonomyAccount(Base):
    __tablename__ = "taxonomy_accounts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    taxonomy_version: Mapped[str] = mapped_column(sa.String(50))
    canonical_code: Mapped[str] = mapped_column(sa.String(100))
    name_pt: Mapped[str] = mapped_column(sa.String(300))
    statement_type: Mapped[str] = mapped_column(sa.String(20))
    parent_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("taxonomy_accounts.id", ondelete="RESTRICT"))
    normal_balance: Mapped[str | None] = mapped_column(sa.String(10))

    __table_args__ = (
        sa.UniqueConstraint("taxonomy_version", "canonical_code", name="uq_taxonomy_accounts_version_code"),
    )


class AccountMappingRule(Base):
    __tablename__ = "account_mapping_rules"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    rule_set: Mapped[str] = mapped_column(sa.String(100))
    version: Mapped[int]
    priority: Mapped[int]
    source_statement_type: Mapped[str] = mapped_column(sa.String(20))
    source_code_pattern: Mapped[str] = mapped_column(sa.String(300))
    issuer_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("issuers.id", ondelete="CASCADE"))
    taxonomy_account_id: Mapped[UUID] = mapped_column(sa.ForeignKey("taxonomy_accounts.id", ondelete="RESTRICT"))
    valid_from: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint("rule_set", "version", "priority", name="uq_account_mapping_rules_priority"),
        sa.CheckConstraint("version > 0", name="positive_version"),
        sa.CheckConstraint("priority >= 0", name="nonnegative_priority"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="valid_window"),
    )


class FinancialFact(Base):
    __tablename__ = "financial_facts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    issuer_id: Mapped[UUID] = mapped_column(sa.ForeignKey("issuers.id", ondelete="CASCADE"), index=True)
    reporting_period_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("reporting_periods.id", ondelete="CASCADE"), index=True
    )
    statement_type: Mapped[str] = mapped_column(sa.String(20))
    consolidation_scope: Mapped[str] = mapped_column(sa.String(20))
    original_account_code: Mapped[str] = mapped_column(sa.String(100))
    original_account_label: Mapped[str] = mapped_column(sa.String(500))
    taxonomy_account_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("taxonomy_accounts.id", ondelete="RESTRICT"), index=True
    )
    value: Mapped[Decimal | None] = mapped_column(sa.Numeric(28, 8))
    currency_code: Mapped[str] = mapped_column(sa.String(3))
    scale_factor: Mapped[int]
    value_status: Mapped[str] = mapped_column(sa.String(20))
    source_object_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("source_object_versions.id", ondelete="RESTRICT"), index=True
    )
    parser_version: Mapped[str] = mapped_column(sa.String(100))
    mapping_rule_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("account_mapping_rules.id", ondelete="RESTRICT"))
    published_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    validated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    knowledge_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)
    valid_from: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    revision_number: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint(
            "reporting_period_id",
            "statement_type",
            "consolidation_scope",
            "original_account_code",
            "revision_number",
            name="uq_financial_facts_business_revision",
        ),
        sa.CheckConstraint(
            "value_status IN ('reported', 'calculated', 'missing', 'not_applicable', 'parse_error', 'suppressed')",
            name="value_status_values",
        ),
        sa.CheckConstraint(
            "((value_status IN ('reported', 'calculated')) AND value IS NOT NULL) OR "
            "((value_status IN ('missing', 'not_applicable', 'parse_error', 'suppressed')) AND value IS NULL)",
            name="value_matches_status",
        ),
        sa.CheckConstraint("scale_factor > 0", name="positive_scale"),
        sa.CheckConstraint("revision_number > 0", name="positive_revision"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="valid_window"),
        sa.CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name="currency_code_format"),
    )


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(sa.String(100))
    version: Mapped[int]
    formula: Mapped[str] = mapped_column(sa.Text)
    unit: Mapped[str] = mapped_column(sa.String(30))
    frequency: Mapped[str] = mapped_column(sa.String(30))
    dependencies: Mapped[list[str]] = mapped_column(sa.JSON, default=list)

    __table_args__ = (
        sa.UniqueConstraint("name", "version", name="uq_metric_definitions_name_version"),
        sa.CheckConstraint("version > 0", name="positive_version"),
    )


class MetricObservation(Base):
    __tablename__ = "metric_observations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    issuer_id: Mapped[UUID] = mapped_column(sa.ForeignKey("issuers.id", ondelete="CASCADE"), index=True)
    reporting_period_id: Mapped[UUID] = mapped_column(sa.ForeignKey("reporting_periods.id", ondelete="CASCADE"))
    metric_definition_id: Mapped[UUID] = mapped_column(sa.ForeignKey("metric_definitions.id", ondelete="RESTRICT"))
    value: Mapped[Decimal | None] = mapped_column(sa.Numeric(28, 10))
    value_status: Mapped[str] = mapped_column(sa.String(20))
    quality_score: Mapped[Decimal] = mapped_column(sa.Numeric(5, 4))
    coverage_ratio: Mapped[Decimal] = mapped_column(sa.Numeric(5, 4))
    data_as_of: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)
    calculation_version: Mapped[str] = mapped_column(sa.String(100))

    __table_args__ = (
        sa.UniqueConstraint(
            "issuer_id",
            "reporting_period_id",
            "metric_definition_id",
            "data_as_of",
            name="uq_metric_observations_as_of",
        ),
        sa.CheckConstraint("quality_score BETWEEN 0 AND 1", name="quality_range"),
        sa.CheckConstraint("coverage_ratio BETWEEN 0 AND 1", name="coverage_range"),
    )


class MetricFactLineage(Base):
    __tablename__ = "metric_fact_lineage"

    metric_observation_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("metric_observations.id", ondelete="CASCADE"), primary_key=True
    )
    financial_fact_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("financial_facts.id", ondelete="RESTRICT"), primary_key=True
    )
    input_role: Mapped[str] = mapped_column(sa.String(100))
