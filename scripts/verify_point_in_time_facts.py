"""Verify fact revision and point-in-time queries against local PostgreSQL."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import sqlalchemy as sa

from database.core import session_scope
from database.models.data_foundation import SourceObjectVersion
from database.models.financial_facts import ReportingPeriod
from ia_investing.application.financial_facts import FinancialFactInput, FinancialFactRepository


async def main() -> None:
    sector_id, industry_id, issuer_id, period_id = (uuid4() for _ in range(4))
    account_code = f"fixture-{uuid4()}"
    async with session_scope() as session:
        source_version_id = await session.scalar(sa.select(SourceObjectVersion.id).limit(1))
        if source_version_id is None:
            raise RuntimeError("run scripts/verify_raw_zone.py before this verification")
        await session.execute(
            sa.text("INSERT INTO sectors (id, name_pt) VALUES (:id, 'Fixture PIT')"), {"id": sector_id}
        )
        await session.execute(
            sa.text("INSERT INTO industries (id, name_pt, sector_id) VALUES (:id, 'Fixture PIT', :sector)"),
            {"id": industry_id, "sector": sector_id},
        )
        await session.execute(
            sa.text("INSERT INTO issuers (id, name_pt, industry_id) VALUES (:id, 'Emissor PIT', :industry)"),
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

    known_at_1 = datetime(2026, 3, 1, 12, tzinfo=UTC)
    common = {
        "issuer_id": issuer_id,
        "reporting_period_id": period_id,
        "statement_type": "DRE",
        "consolidation_scope": "consolidated",
        "original_account_code": account_code,
        "original_account_label": "Receita fixture",
        "taxonomy_account_id": None,
        "currency_code": "BRL",
        "scale_factor": 1,
        "value_status": "reported",
        "source_object_version_id": source_version_id,
        "parser_version": "fixture-v1",
        "mapping_rule_id": None,
        "published_at": known_at_1 - timedelta(days=1),
        "discovered_at": known_at_1,
        "ingested_at": known_at_1,
        "validated_at": known_at_1,
    }
    first_input = FinancialFactInput(value=Decimal("100.00"), knowledge_at=known_at_1, **common)
    async with session_scope() as session:
        first = await FinancialFactRepository(session).revise(first_input)
    known_at_2 = known_at_1 + timedelta(days=30)
    second_input = FinancialFactInput(
        value=Decimal("125.00"),
        knowledge_at=known_at_2,
        **{
            **common,
            "published_at": known_at_2 - timedelta(days=1),
            "discovered_at": known_at_2,
            "ingested_at": known_at_2,
            "validated_at": known_at_2,
        },
    )
    async with session_scope() as session:
        second = await FinancialFactRepository(session).revise(second_input)
    async with session_scope() as session:
        repeated = await FinancialFactRepository(session).revise(second_input)
        before = await FinancialFactRepository(session).list_as_of(
            issuer_id, period_id, known_at_1 + timedelta(minutes=1)
        )
        after = await FinancialFactRepository(session).list_as_of(
            issuer_id, period_id, known_at_2 + timedelta(minutes=1)
        )

    assert first.created and second.created and not repeated.created
    assert before[0].value == Decimal("100.00000000")
    assert after[0].value == Decimal("125.00000000")
    assert before[0].id != after[0].id
    print("point-in-time-ok revisions=1,2 before=100 after=125 idempotent=true")


if __name__ == "__main__":
    asyncio.run(main())
