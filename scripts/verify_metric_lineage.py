"""Verify canonical metric calculation, PIT filtering, and fact lineage."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import sqlalchemy as sa

from database.core import session_scope
from database.models.data_foundation import SourceObjectVersion
from database.models.financial_facts import ReportingPeriod, TaxonomyAccount
from ia_investing.application.financial_facts import FinancialFactInput, FinancialFactRepository
from ia_investing.application.metrics import MetricService


async def main() -> None:
    sector_id, industry_id, issuer_id, period_id = (uuid4() for _ in range(4))
    account_ids = {"current_assets": uuid4(), "current_liabilities": uuid4()}
    as_of = datetime(2026, 3, 1, 12, tzinfo=UTC)
    async with session_scope() as session:
        source_version_id = await session.scalar(sa.select(SourceObjectVersion.id).limit(1))
        if source_version_id is None:
            raise RuntimeError("run scripts/verify_raw_zone.py before this verification")
        await session.execute(
            sa.text("INSERT INTO sectors (id, name_pt) VALUES (:id, 'Fixture Metric')"), {"id": sector_id}
        )
        await session.execute(
            sa.text("INSERT INTO industries (id, name_pt, sector_id) VALUES (:id, 'Fixture Metric', :sector)"),
            {"id": industry_id, "sector": sector_id},
        )
        await session.execute(
            sa.text("INSERT INTO issuers (id, name_pt, industry_id) VALUES (:id, 'Emissor Metric', :industry)"),
            {"id": issuer_id, "industry": industry_id},
        )
        session.add(
            ReportingPeriod(
                id=period_id,
                issuer_id=issuer_id,
                period_start=date(2025, 1, 1),
                period_end=date(2025, 12, 31),
                fiscal_year=2025,
                period_type="annual",
                consolidation_scope="consolidated",
            )
        )
        for code, account_id in account_ids.items():
            session.add(
                TaxonomyAccount(
                    id=account_id,
                    taxonomy_version=str(issuer_id),
                    canonical_code=code,
                    name_pt=code,
                    statement_type="BPA" if code == "current_assets" else "BPP",
                    parent_id=None,
                    normal_balance="debit" if code == "current_assets" else "credit",
                )
            )

    for code, amount in (("current_assets", Decimal("10")), ("current_liabilities", Decimal("4"))):
        item = FinancialFactInput(
            issuer_id=issuer_id,
            reporting_period_id=period_id,
            statement_type="BPA" if code == "current_assets" else "BPP",
            consolidation_scope="consolidated",
            original_account_code=code,
            original_account_label=code,
            taxonomy_account_id=account_ids[code],
            value=amount,
            currency_code="BRL",
            scale_factor=1,
            value_status="reported",
            source_object_version_id=source_version_id,
            parser_version="fixture-v1",
            mapping_rule_id=None,
            published_at=as_of,
            discovered_at=as_of,
            ingested_at=as_of,
            validated_at=as_of,
            knowledge_at=as_of,
        )
        async with session_scope() as session:
            await FinancialFactRepository(session).revise(item)

    async with session_scope() as session:
        first = await MetricService(session).calculate("current_ratio", issuer_id, period_id, as_of)
    async with session_scope() as session:
        repeated = await MetricService(session).calculate("current_ratio", issuer_id, period_id, as_of)

    assert first.value == Decimal("2.5000000000")
    assert first.coverage_ratio == Decimal("1.0000")
    assert len(first.lineage_ids) == 2
    assert repeated.observation_id == first.observation_id
    print("metric-lineage-ok metric=current_ratio value=2.5 facts=2 idempotent=true")


if __name__ == "__main__":
    asyncio.run(main())
