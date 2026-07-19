"""quality incidents and quarantine

Revision ID: a2f100000004
Revises: a2f100000003
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a2f100000004"
down_revision: str | Sequence[str] | None = "a2f100000003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quality_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("is_material", sa.Boolean(), nullable=False),
        sa.Column("tolerance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "severity IN ('critical', 'error', 'warning', 'info')",
            name=op.f("ck_quality_rules_severity_values"),
        ),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name=op.f("ck_quality_rules_valid_window")),
        sa.CheckConstraint("version > 0", name=op.f("ck_quality_rules_positive_version")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quality_rules")),
        sa.UniqueConstraint("code", "version", name="uq_quality_rules_code_version"),
    )
    op.create_table(
        "quality_incidents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("quality_rule_id", sa.UUID(), nullable=False),
        sa.Column("source_object_version_id", sa.UUID(), nullable=False),
        sa.Column("financial_fact_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("owner_role", sa.String(100), nullable=False),
        sa.Column("impact_summary", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("waiver_reason", sa.Text(), nullable=True),
        sa.Column("waiver_approved_by", sa.String(255), nullable=True),
        sa.Column("waiver_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "severity IN ('critical', 'error', 'warning', 'info')",
            name=op.f("ck_quality_incidents_severity_values"),
        ),
        sa.CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved', 'waived')",
            name=op.f("ck_quality_incidents_status_values"),
        ),
        sa.CheckConstraint(
            "status <> 'waived' OR (waiver_reason IS NOT NULL AND waiver_approved_by IS NOT NULL "
            "AND waiver_expires_at IS NOT NULL)",
            name=op.f("ck_quality_incidents_waiver_fields_required"),
        ),
        sa.ForeignKeyConstraint(
            ["financial_fact_id"],
            ["financial_facts.id"],
            name=op.f("fk_quality_incidents_financial_fact_id_financial_facts"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["quality_rule_id"],
            ["quality_rules.id"],
            name=op.f("fk_quality_incidents_quality_rule_id_quality_rules"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_object_version_id"],
            ["source_object_versions.id"],
            name=op.f("fk_quality_incidents_source_object_version_id_source_object_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quality_incidents")),
        sa.UniqueConstraint(
            "quality_rule_id",
            "source_object_version_id",
            name="uq_quality_incidents_rule_source_version",
        ),
    )
    op.bulk_insert(
        sa.table(
            "quality_rules",
            sa.column("id", sa.UUID()),
            sa.column("code", sa.String()),
            sa.column("version", sa.Integer()),
            sa.column("severity", sa.String()),
            sa.column("is_material", sa.Boolean()),
            sa.column("tolerance", postgresql.JSONB()),
            sa.column("valid_from", sa.DateTime(timezone=True)),
        ),
        [
            {
                "id": "40000000-0000-0000-0000-000000000001",
                "code": "balance_sheet_balances",
                "version": 1,
                "severity": "critical",
                "is_material": True,
                "tolerance": {"relative": "0.001"},
                "valid_from": datetime(2026, 7, 18, tzinfo=UTC),
            }
        ],
    )
    op.create_index(op.f("ix_quality_incidents_quality_rule_id"), "quality_incidents", ["quality_rule_id"])
    op.create_index(
        op.f("ix_quality_incidents_source_object_version_id"), "quality_incidents", ["source_object_version_id"]
    )
    op.create_table(
        "quarantine_records",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_object_version_id", sa.UUID(), nullable=False),
        sa.Column("quality_incident_id", sa.UUID(), nullable=False),
        sa.Column("stage", sa.String(50), nullable=False),
        sa.Column("payload_reference", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('blocked', 'released', 'discarded')",
            name=op.f("ck_quarantine_records_status_values"),
        ),
        sa.ForeignKeyConstraint(
            ["quality_incident_id"],
            ["quality_incidents.id"],
            name=op.f("fk_quarantine_records_quality_incident_id_quality_incidents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_object_version_id"],
            ["source_object_versions.id"],
            name=op.f("fk_quarantine_records_source_object_version_id_source_object_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quarantine_records")),
        sa.UniqueConstraint("quality_incident_id", name=op.f("uq_quarantine_records_quality_incident_id")),
    )
    op.create_index(
        op.f("ix_quarantine_records_source_object_version_id"), "quarantine_records", ["source_object_version_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_quarantine_records_source_object_version_id"), table_name="quarantine_records")
    op.drop_table("quarantine_records")
    op.drop_index(op.f("ix_quality_incidents_source_object_version_id"), table_name="quality_incidents")
    op.drop_index(op.f("ix_quality_incidents_quality_rule_id"), table_name="quality_incidents")
    op.drop_table("quality_incidents")
    op.drop_table("quality_rules")
