"""seed official policy and macro sources

Revision ID: f7a100000001
Revises: d17057502a53
Create Date: 2026-07-18
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "f7a100000001"
down_revision: str | Sequence[str] | None = "d17057502a53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LICENSE_ID = "27000000-0000-0000-0000-000000000001"
CREATED_AT = datetime(2026, 7, 18, tzinfo=UTC)
SOURCES = (
    (
        "27000000-0000-0000-0001-000000000001",
        "camara-dados-abertos",
        "Câmara dos Deputados — Dados Abertos",
        "https://dadosabertos.camara.leg.br/api/v2/",
        None,
        "api-v2",
        60,
        60,
        30,
    ),
    (
        "27000000-0000-0000-0002-000000000001",
        "senado-dados-abertos",
        "Senado Federal — Dados Abertos Legislativos",
        "https://legis.senado.leg.br/dadosabertos/",
        None,
        "swagger-current",
        30,
        60,
        30,
    ),
    (
        "27000000-0000-0000-0003-000000000001",
        "dou-inlabs",
        "Imprensa Nacional — INLABS",
        "https://inlabs.in.gov.br/",
        "secret://data-sources/inlabs",
        "xml-current",
        20,
        1_440,
        180,
    ),
    (
        "27000000-0000-0000-0004-000000000001",
        "bcb-sgs",
        "Banco Central do Brasil — SGS",
        "https://api.bcb.gov.br/dados/serie/",
        None,
        "json-current",
        30,
        1_440,
        180,
    ),
    (
        "27000000-0000-0000-0005-000000000001",
        "ibge-sidra",
        "IBGE — SIDRA",
        "https://apisidra.ibge.gov.br/values/",
        None,
        "json-current",
        30,
        1_440,
        180,
    ),
)


def upgrade() -> None:
    licenses = sa.table(
        "source_licenses",
        sa.column("id", sa.UUID()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("terms_url", sa.Text()),
        sa.column("permits_redistribution", sa.Boolean()),
        sa.column("retention_days", sa.Integer()),
        sa.column("reviewed_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        licenses,
        [
            {
                "id": LICENSE_ID,
                "code": "official-public-access-legal-review-required",
                "name": "Official public access; redistribution and retention require legal review",
                "terms_url": "https://www.gov.br/governodigital/pt-br/dados-abertos",
                "permits_redistribution": False,
                "retention_days": None,
                "reviewed_at": None,
            }
        ],
    )
    data_sources = sa.table(
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
    )
    op.bulk_insert(
        data_sources,
        [
            {
                "id": source_id,
                "code": code,
                "name": name,
                "base_url": base_url,
                "owner_role": "data-steward-policy-macro",
                "credential_reference": credential_reference,
                "schema_version": schema_version,
                "rate_limit_per_minute": rate_limit,
                "license_id": LICENSE_ID,
                "is_active": True,
                "created_at": CREATED_AT,
            }
            for (
                source_id,
                code,
                name,
                base_url,
                credential_reference,
                schema_version,
                rate_limit,
                _frequency,
                _grace,
            ) in SOURCES
        ],
    )
    source_slas = sa.table(
        "source_slas",
        sa.column("id", sa.UUID()),
        sa.column("source_id", sa.UUID()),
        sa.column("expected_frequency_minutes", sa.Integer()),
        sa.column("freshness_grace_minutes", sa.Integer()),
    )
    op.bulk_insert(
        source_slas,
        [
            {
                "id": f"27000000-0000-0000-0010-{index:012d}",
                "source_id": source_id,
                "expected_frequency_minutes": frequency,
                "freshness_grace_minutes": grace,
            }
            for index, (
                source_id,
                _code,
                _name,
                _base_url,
                _credential_reference,
                _schema,
                _rate,
                frequency,
                grace,
            ) in enumerate(SOURCES, start=1)
        ],
    )


def downgrade() -> None:
    source_ids = [item[0] for item in SOURCES]
    op.execute(sa.text("DELETE FROM source_slas WHERE source_id = ANY(:ids)").bindparams(ids=source_ids))
    op.execute(sa.text("DELETE FROM data_sources WHERE id = ANY(:ids)").bindparams(ids=source_ids))
    op.execute(sa.text("DELETE FROM source_licenses WHERE id = :id").bindparams(id=LICENSE_ID))
