"""seed official policy and macro sources

Revision ID: f7a100000001
Revises: d17057502a53
Create Date: 2026-07-18
"""

from collections.abc import Sequence
from datetime import UTC, datetime

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
    # Seed data moved to scripts/seed_initial_data.py — run `make init`.
    pass


def downgrade() -> None:
    # Seed data removed from migrations — managed by scripts/seed_initial_data.py.
    pass
