"""Idempotent seed for reference data.

Run via ``make init`` or directly:
    uv run python scripts/seed_initial_data.py

All inserts use ON CONFLICT DO NOTHING so the script is safe to re-run.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# Allow running from repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from database.core import session_scope

UTCNOW = datetime.now(UTC)

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

SOURCE_LICENSES = [
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
    {
        "id": "27000000-0000-0000-0000-000000000001",
        "code": "official-public-access-legal-review-required",
        "name": "Official public access; redistribution and retention require legal review",
        "terms_url": "https://www.gov.br/governodigital/pt-br/dados-abertos",
        "permits_redistribution": False,
    },
]

DATA_SOURCES = [
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
    },
    {
        "id": "27000000-0000-0000-0001-000000000001",
        "code": "camara-dados-abertos",
        "name": "Câmara dos Deputados — Dados Abertos",
        "base_url": "https://dadosabertos.camara.leg.br/api/v2/",
        "owner_role": "data-steward-policy-macro",
        "credential_reference": None,
        "schema_version": "api-v2",
        "rate_limit_per_minute": 60,
        "license_id": "27000000-0000-0000-0000-000000000001",
    },
    {
        "id": "27000000-0000-0000-0002-000000000001",
        "code": "senado-dados-abertos",
        "name": "Senado Federal — Dados Abertos Legislativos",
        "base_url": "https://legis.senado.leg.br/dadosabertos/",
        "owner_role": "data-steward-policy-macro",
        "credential_reference": None,
        "schema_version": "swagger-current",
        "rate_limit_per_minute": 30,
        "license_id": "27000000-0000-0000-0000-000000000001",
    },
    {
        "id": "27000000-0000-0000-0003-000000000001",
        "code": "dou-inlabs",
        "name": "Imprensa Nacional — INLABS",
        "base_url": "https://inlabs.in.gov.br/",
        "owner_role": "data-steward-policy-macro",
        "credential_reference": "secret://data-sources/inlabs",
        "schema_version": "xml-current",
        "rate_limit_per_minute": 20,
        "license_id": "27000000-0000-0000-0000-000000000001",
    },
    {
        "id": "27000000-0000-0000-0004-000000000001",
        "code": "bcb-sgs",
        "name": "Banco Central do Brasil — SGS",
        "base_url": "https://api.bcb.gov.br/dados/serie/",
        "owner_role": "data-steward-policy-macro",
        "credential_reference": None,
        "schema_version": "json-current",
        "rate_limit_per_minute": 30,
        "license_id": "27000000-0000-0000-0000-000000000001",
    },
    {
        "id": "27000000-0000-0000-0005-000000000001",
        "code": "ibge-sidra",
        "name": "IBGE — SIDRA",
        "base_url": "https://apisidra.ibge.gov.br/values/",
        "owner_role": "data-steward-policy-macro",
        "credential_reference": None,
        "schema_version": "json-current",
        "rate_limit_per_minute": 30,
        "license_id": "27000000-0000-0000-0000-000000000001",
    },
]

SOURCE_SLAS = [
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
    {
        "id": "27000000-0000-0000-0010-000000000001",
        "source_id": "27000000-0000-0000-0001-000000000001",
        "expected_frequency_minutes": 60,
        "freshness_grace_minutes": 30,
    },
    {
        "id": "27000000-0000-0000-0010-000000000002",
        "source_id": "27000000-0000-0000-0002-000000000001",
        "expected_frequency_minutes": 30,
        "freshness_grace_minutes": 30,
    },
    {
        "id": "27000000-0000-0000-0010-000000000003",
        "source_id": "27000000-0000-0000-0003-000000000001",
        "expected_frequency_minutes": 1440,
        "freshness_grace_minutes": 180,
    },
    {
        "id": "27000000-0000-0000-0010-000000000004",
        "source_id": "27000000-0000-0000-0004-000000000001",
        "expected_frequency_minutes": 1440,
        "freshness_grace_minutes": 180,
    },
    {
        "id": "27000000-0000-0000-0010-000000000005",
        "source_id": "27000000-0000-0000-0005-000000000001",
        "expected_frequency_minutes": 1440,
        "freshness_grace_minutes": 180,
    },
]

QUALITY_RULES = [
    {
        "id": "40000000-0000-0000-0000-000000000001",
        "code": "balance_sheet_balances",
        "version": 1,
        "severity": "critical",
        "is_material": True,
        "tolerance": {"relative": "0.001"},
        "valid_from": UTCNOW,
    },
]

METRIC_DEFINITIONS = [
    {
        "id": "50000000-0000-0000-0000-000000000001",
        "name": "current_ratio",
        "version": 1,
        "formula": "current_assets / current_liabilities",
        "unit": "ratio",
        "frequency": "quarterly",
        "dependencies": ["current_assets", "current_liabilities"],
    },
    {
        "id": "50000000-0000-0000-0000-000000000002",
        "name": "net_margin",
        "version": 1,
        "formula": "net_income / revenue",
        "unit": "ratio",
        "frequency": "quarterly",
        "dependencies": ["net_income", "revenue"],
    },
    {
        "id": "50000000-0000-0000-0000-000000000003",
        "name": "debt_to_equity",
        "version": 1,
        "formula": "total_debt / equity",
        "unit": "ratio",
        "frequency": "quarterly",
        "dependencies": ["total_debt", "equity"],
    },
]


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------


async def _upsert(session: AsyncSession, table: str, rows: list[dict], unique_cols: list[str]) -> int:
    if not rows:
        return 0
    stmt = pg_insert(sa.table(table, *[sa.column(k) for k in rows[0]])).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=unique_cols)
    result = await session.execute(stmt)
    return result.rowcount  # type: ignore[return-value]


async def seed() -> None:
    async with session_scope() as session:
        n = await _upsert(session, "source_licenses", SOURCE_LICENSES, ["id"])
        print(f"  source_licenses: {n} inserted")
        data_sources = [{**row, "is_active": True, "created_at": UTCNOW} for row in DATA_SOURCES]
        n = await _upsert(session, "data_sources", data_sources, ["id"])
        print(f"  data_sources:    {n} inserted")
        n = await _upsert(session, "source_slas", SOURCE_SLAS, ["id"])
        print(f"  source_slas:     {n} inserted")
        quality_rules = [{**row, "tolerance": json.dumps(row["tolerance"])} for row in QUALITY_RULES]
        n = await _upsert(session, "quality_rules", quality_rules, ["id"])
        print(f"  quality_rules:   {n} inserted")
        metric_definitions = [{**row, "dependencies": json.dumps(row["dependencies"])} for row in METRIC_DEFINITIONS]
        n = await _upsert(session, "metric_definitions", metric_definitions, ["id"])
        print(f"  metric_defs:     {n} inserted")
        await session.commit()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
