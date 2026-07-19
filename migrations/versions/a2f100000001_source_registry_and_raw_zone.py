"""source registry and versioned raw zone

Revision ID: a2f100000001
Revises: fd3d46f598f2
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a2f100000001"
down_revision: str | Sequence[str] | None = "fd3d46f598f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_licenses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("terms_url", sa.Text(), nullable=True),
        sa.Column("permits_redistribution", sa.Boolean(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_licenses")),
        sa.UniqueConstraint("code", name=op.f("uq_source_licenses_code")),
    )
    op.create_table(
        "data_sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("owner_role", sa.String(100), nullable=False),
        sa.Column("credential_reference", sa.String(300), nullable=True),
        sa.Column("schema_version", sa.String(50), nullable=False),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=True),
        sa.Column("license_id", sa.UUID(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "rate_limit_per_minute IS NULL OR rate_limit_per_minute > 0",
            name=op.f("ck_data_sources_positive_rate_limit"),
        ),
        sa.ForeignKeyConstraint(
            ["license_id"],
            ["source_licenses.id"],
            name=op.f("fk_data_sources_license_id_source_licenses"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_sources")),
        sa.UniqueConstraint("code", name=op.f("uq_data_sources_code")),
    )
    op.create_table(
        "source_slas",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("expected_frequency_minutes", sa.Integer(), nullable=False),
        sa.Column("freshness_grace_minutes", sa.Integer(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(100), nullable=True),
        sa.CheckConstraint("expected_frequency_minutes > 0", name=op.f("ck_source_slas_positive_frequency")),
        sa.CheckConstraint("freshness_grace_minutes >= 0", name=op.f("ck_source_slas_nonnegative_freshness_grace")),
        sa.ForeignKeyConstraint(
            ["source_id"], ["data_sources.id"], name=op.f("fk_source_slas_source_id_data_sources"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_slas")),
        sa.UniqueConstraint("source_id", name=op.f("uq_source_slas_source_id")),
    )
    op.create_table(
        "source_objects",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("logical_uri", sa.Text(), nullable=False),
        sa.Column("object_type", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["data_sources.id"],
            name=op.f("fk_source_objects_source_id_data_sources"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_objects")),
        sa.UniqueConstraint("source_id", "logical_uri", name="uq_source_objects_source_uri"),
    )
    op.create_index(op.f("ix_source_objects_source_id"), "source_objects", ["source_id"])
    op.create_table(
        "source_object_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_object_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("etag", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(200), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("parser_version", sa.String(100), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_source_object_versions_sha256_format")),
        sa.CheckConstraint("size_bytes >= 0", name=op.f("ck_source_object_versions_nonnegative_size")),
        sa.CheckConstraint("version_number > 0", name=op.f("ck_source_object_versions_positive_version")),
        sa.ForeignKeyConstraint(
            ["source_object_id"],
            ["source_objects.id"],
            name=op.f("fk_source_object_versions_source_object_id_source_objects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_object_versions")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_source_object_versions_storage_key")),
        sa.UniqueConstraint("source_object_id", "content_sha256", name="uq_source_object_versions_hash"),
        sa.UniqueConstraint("source_object_id", "version_number", name="uq_source_object_versions_number"),
    )
    op.create_index(op.f("ix_source_object_versions_source_object_id"), "source_object_versions", ["source_object_id"])
    op.create_table(
        "ingestion_attempts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_object_id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.String(255), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint("attempt_number > 0", name=op.f("ck_ingestion_attempts_positive_attempt")),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'quarantined')",
            name=op.f("ck_ingestion_attempts_status_values"),
        ),
        sa.ForeignKeyConstraint(
            ["source_object_id"],
            ["source_objects.id"],
            name=op.f("fk_ingestion_attempts_source_object_id_source_objects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_attempts")),
        sa.UniqueConstraint("workflow_id", "attempt_number", name="uq_ingestion_attempts_workflow_attempt"),
    )
    op.create_index(op.f("ix_ingestion_attempts_source_object_id"), "ingestion_attempts", ["source_object_id"])
    op.bulk_insert(
        sa.table(
            "source_licenses",
            sa.column("id", sa.UUID()),
            sa.column("code", sa.String()),
            sa.column("name", sa.String()),
            sa.column("terms_url", sa.Text()),
            sa.column("permits_redistribution", sa.Boolean()),
        ),
        [
            {
                "id": "20000000-0000-0000-0000-000000000001",
                "code": "CVM-OFFICIAL",
                "name": "Dados oficiais CVM — revisão jurídica obrigatória",
                "terms_url": "https://dados.cvm.gov.br/",
                "permits_redistribution": False,
            },
            {
                "id": "20000000-0000-0000-0000-000000000002",
                "code": "B3-OFFICIAL",
                "name": "Dados oficiais B3 — contrato/licença aplicável",
                "terms_url": "https://www.b3.com.br/",
                "permits_redistribution": False,
            },
        ],
    )
    op.bulk_insert(
        sa.table(
            "data_sources",
            sa.column("id", sa.UUID()),
            sa.column("code", sa.String()),
            sa.column("name", sa.String()),
            sa.column("base_url", sa.Text()),
            sa.column("owner_role", sa.String()),
            sa.column("credential_reference", sa.String()),
            sa.column("schema_version", sa.String()),
            sa.column("rate_limit_per_minute", sa.Integer()),
            sa.column("license_id", sa.UUID()),
            sa.column("is_active", sa.Boolean()),
            sa.column("created_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "id": "21000000-0000-0000-0000-000000000001",
                "code": "CVM",
                "name": "Comissão de Valores Mobiliários",
                "base_url": "https://dados.cvm.gov.br/",
                "owner_role": "data-steward-cvm",
                "credential_reference": None,
                "schema_version": "open-data-v1",
                "rate_limit_per_minute": 30,
                "license_id": "20000000-0000-0000-0000-000000000001",
                "is_active": True,
                "created_at": datetime(2026, 7, 18, tzinfo=UTC),
            },
            {
                "id": "21000000-0000-0000-0000-000000000002",
                "code": "B3",
                "name": "B3 S.A.",
                "base_url": "https://www.b3.com.br/",
                "owner_role": "data-steward-b3",
                "credential_reference": "secret://data-sources/b3",
                "schema_version": "contract-v1",
                "rate_limit_per_minute": 10,
                "license_id": "20000000-0000-0000-0000-000000000002",
                "is_active": True,
                "created_at": datetime(2026, 7, 18, tzinfo=UTC),
            },
        ],
    )
    op.bulk_insert(
        sa.table(
            "source_slas",
            sa.column("id", sa.UUID()),
            sa.column("source_id", sa.UUID()),
            sa.column("expected_frequency_minutes", sa.Integer()),
            sa.column("freshness_grace_minutes", sa.Integer()),
        ),
        [
            {
                "id": "22000000-0000-0000-0000-000000000001",
                "source_id": "21000000-0000-0000-0000-000000000001",
                "expected_frequency_minutes": 1440,
                "freshness_grace_minutes": 360,
            },
            {
                "id": "22000000-0000-0000-0000-000000000002",
                "source_id": "21000000-0000-0000-0000-000000000002",
                "expected_frequency_minutes": 1440,
                "freshness_grace_minutes": 360,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ingestion_attempts_source_object_id"), table_name="ingestion_attempts")
    op.drop_table("ingestion_attempts")
    op.drop_index(op.f("ix_source_object_versions_source_object_id"), table_name="source_object_versions")
    op.drop_table("source_object_versions")
    op.drop_index(op.f("ix_source_objects_source_id"), table_name="source_objects")
    op.drop_table("source_objects")
    op.drop_table("source_slas")
    op.drop_table("data_sources")
    op.drop_table("source_licenses")
