from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class ValuationRun(Base):
    __tablename__ = "valuation_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    thesis_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("research_thesis_versions.id", ondelete="CASCADE"), index=True
    )
    model_type: Mapped[str] = mapped_column(sa.String(30))
    code_version: Mapped[str] = mapped_column(sa.String(100))
    input_sha256: Mapped[str] = mapped_column(sa.String(64))
    input_payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    result_sha256: Mapped[str] = mapped_column(sa.String(64))
    data_as_of: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    status: Mapped[str] = mapped_column(sa.String(20), default="completed")
    created_by: Mapped[str] = mapped_column(sa.String(255))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint("thesis_version_id", "model_type", "input_sha256", name="uq_valuation_runs_input"),
        sa.CheckConstraint("input_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        sa.CheckConstraint("result_sha256 ~ '^[0-9a-f]{64}$'", name="result_sha256_format"),
        sa.CheckConstraint("status IN ('completed', 'failed', 'blocked')", name="status_values"),
    )


class ValuationAssumption(Base):
    __tablename__ = "valuation_assumptions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    valuation_run_id: Mapped[UUID] = mapped_column(sa.ForeignKey("valuation_runs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(sa.String(100))
    value: Mapped[Decimal] = mapped_column(sa.Numeric(28, 10))
    unit: Mapped[str] = mapped_column(sa.String(30))
    horizon: Mapped[str] = mapped_column(sa.String(50))
    evidence_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("research_evidence.id", ondelete="RESTRICT"))
    financial_fact_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("financial_facts.id", ondelete="RESTRICT"))
    metric_observation_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("metric_observations.id", ondelete="RESTRICT")
    )
    source_version: Mapped[str] = mapped_column(sa.String(100))
    approved_by: Mapped[str] = mapped_column(sa.String(255))
    sensitivity_low: Mapped[Decimal | None] = mapped_column(sa.Numeric(28, 10))
    sensitivity_high: Mapped[Decimal | None] = mapped_column(sa.Numeric(28, 10))

    __table_args__ = (
        sa.UniqueConstraint("valuation_run_id", "name", name="uq_valuation_assumptions_run_name"),
        sa.CheckConstraint(
            "num_nonnulls(evidence_id, financial_fact_id, metric_observation_id) = 1",
            name="exactly_one_source",
        ),
        sa.CheckConstraint(
            "sensitivity_low IS NULL OR sensitivity_high IS NULL OR sensitivity_low <= sensitivity_high",
            name="valid_sensitivity",
        ),
    )


class ValuationResult(Base):
    __tablename__ = "valuation_results"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    valuation_run_id: Mapped[UUID] = mapped_column(sa.ForeignKey("valuation_runs.id", ondelete="CASCADE"), index=True)
    scenario: Mapped[str] = mapped_column(sa.String(30))
    equity_value: Mapped[Decimal] = mapped_column(sa.Numeric(28, 8))
    value_per_share: Mapped[Decimal] = mapped_column(sa.Numeric(28, 8))
    probability: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 4))
    result_payload: Mapped[dict[str, object]] = mapped_column(JSONB)

    __table_args__ = (
        sa.UniqueConstraint("valuation_run_id", "scenario", name="uq_valuation_results_run_scenario"),
        sa.CheckConstraint(
            "scenario IN ('bear', 'base', 'bull', 'weighted', 'reverse_dcf', 'relative')",
            name="scenario_values",
        ),
        sa.CheckConstraint("probability IS NULL OR probability BETWEEN 0 AND 1", name="probability_range"),
    )
