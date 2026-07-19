"""deterministic valuation runs, assumptions, and scenarios

Revision ID: a2f100000011
Revises: a2f100000010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a2f100000011"
down_revision: str | Sequence[str] | None = "a2f100000010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "valuation_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("thesis_version_id", sa.UUID(), nullable=False),
        sa.Column("model_type", sa.String(30), nullable=False),
        sa.Column("code_version", sa.String(100), nullable=False),
        sa.Column("input_sha256", sa.String(64), nullable=False),
        sa.Column("data_as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("input_sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_valuation_runs_sha256_format")),
        sa.CheckConstraint(
            "status IN ('completed', 'failed', 'blocked')", name=op.f("ck_valuation_runs_status_values")
        ),
        sa.ForeignKeyConstraint(
            ["thesis_version_id"],
            ["research_thesis_versions.id"],
            name=op.f("fk_valuation_runs_thesis_version_id_research_thesis_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_valuation_runs")),
        sa.UniqueConstraint("thesis_version_id", "model_type", "input_sha256", name="uq_valuation_runs_input"),
    )
    op.create_index(op.f("ix_valuation_runs_thesis_version_id"), "valuation_runs", ["thesis_version_id"])
    op.create_table(
        "valuation_assumptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("valuation_run_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("value", sa.Numeric(28, 10), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("horizon", sa.String(50), nullable=False),
        sa.Column("evidence_id", sa.UUID(), nullable=True),
        sa.Column("financial_fact_id", sa.UUID(), nullable=True),
        sa.Column("metric_observation_id", sa.UUID(), nullable=True),
        sa.Column("source_version", sa.String(100), nullable=False),
        sa.Column("approved_by", sa.String(255), nullable=False),
        sa.Column("sensitivity_low", sa.Numeric(28, 10), nullable=True),
        sa.Column("sensitivity_high", sa.Numeric(28, 10), nullable=True),
        sa.CheckConstraint(
            "num_nonnulls(evidence_id, financial_fact_id, metric_observation_id) = 1",
            name=op.f("ck_valuation_assumptions_exactly_one_source"),
        ),
        sa.CheckConstraint(
            "sensitivity_low IS NULL OR sensitivity_high IS NULL OR sensitivity_low <= sensitivity_high",
            name=op.f("ck_valuation_assumptions_valid_sensitivity"),
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["research_evidence.id"],
            name=op.f("fk_valuation_assumptions_evidence_id_research_evidence"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["financial_fact_id"],
            ["financial_facts.id"],
            name=op.f("fk_valuation_assumptions_financial_fact_id_financial_facts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["metric_observation_id"],
            ["metric_observations.id"],
            name=op.f("fk_valuation_assumptions_metric_observation_id_metric_observations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["valuation_run_id"],
            ["valuation_runs.id"],
            name=op.f("fk_valuation_assumptions_valuation_run_id_valuation_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_valuation_assumptions")),
        sa.UniqueConstraint("valuation_run_id", "name", name="uq_valuation_assumptions_run_name"),
    )
    op.create_index(op.f("ix_valuation_assumptions_valuation_run_id"), "valuation_assumptions", ["valuation_run_id"])
    op.create_table(
        "valuation_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("valuation_run_id", sa.UUID(), nullable=False),
        sa.Column("scenario", sa.String(30), nullable=False),
        sa.Column("equity_value", sa.Numeric(28, 8), nullable=False),
        sa.Column("value_per_share", sa.Numeric(28, 8), nullable=False),
        sa.Column("probability", sa.Numeric(5, 4), nullable=True),
        sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "probability IS NULL OR probability BETWEEN 0 AND 1", name=op.f("ck_valuation_results_probability_range")
        ),
        sa.CheckConstraint(
            "scenario IN ('bear', 'base', 'bull', 'weighted', 'reverse_dcf', 'relative')",
            name=op.f("ck_valuation_results_scenario_values"),
        ),
        sa.ForeignKeyConstraint(
            ["valuation_run_id"],
            ["valuation_runs.id"],
            name=op.f("fk_valuation_results_valuation_run_id_valuation_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_valuation_results")),
        sa.UniqueConstraint("valuation_run_id", "scenario", name="uq_valuation_results_run_scenario"),
    )
    op.create_index(op.f("ix_valuation_results_valuation_run_id"), "valuation_results", ["valuation_run_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_valuation_results_valuation_run_id"), table_name="valuation_results")
    op.drop_table("valuation_results")
    op.drop_index(op.f("ix_valuation_assumptions_valuation_run_id"), table_name="valuation_assumptions")
    op.drop_table("valuation_assumptions")
    op.drop_index(op.f("ix_valuation_runs_thesis_version_id"), table_name="valuation_runs")
    op.drop_table("valuation_runs")
