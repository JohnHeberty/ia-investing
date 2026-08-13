"""Integration test: FinancialFact lifecycle — revise, list_as_of, idempotency.

Tests the full round-trip through PostgreSQL:
  1. Create a fact via revise()
  2. Query with list_as_of() before/after knowledge_at
  3. Revise again — verify window closure and revision increment
  4. Idempotent revise — verify created=False
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.catalog import Issuer
from database.models.data_foundation import DataSource, SourceObject, SourceObjectVersion
from database.models.financial_facts import ReportingPeriod
from ia_investing.application.financial_facts import (
    FinancialFactInput,
    FinancialFactRepository,
)

_TZ = UTC


def _dt(y: int, m: int, d: int, h: int = 0, mi: int = 0) -> datetime:
    return datetime(y, m, d, h, mi, tzinfo=_TZ)


def _make_input(**overrides) -> FinancialFactInput:
    defaults = {
        "issuer_id": uuid4(),
        "reporting_period_id": uuid4(),
        "statement_type": "BPA",
        "consolidation_scope": "consolidated",
        "original_account_code": "1.01",
        "original_account_label": "Ativo Circulante",
        "taxonomy_account_id": uuid4(),
        "value": Decimal("5000.00"),
        "currency_code": "BRL",
        "scale_factor": 1,
        "value_status": "reported",
        "source_object_version_id": uuid4(),
        "parser_version": "parser-v1",
        "mapping_rule_id": uuid4(),
        "published_at": _dt(2024, 12, 31),
        "discovered_at": _dt(2024, 12, 31, 23),
        "ingested_at": _dt(2024, 12, 31, 23, 59),
        "validated_at": _dt(2025, 1, 1),
        "knowledge_at": _dt(2025, 1, 2),
    }
    defaults.update(overrides)
    return FinancialFactInput(**defaults)


@pytest.fixture
async def fact_refs(session: AsyncSession) -> dict:
    issuer = Issuer(name_pt=f"Integration Issuer {uuid4()}", is_active=True)
    session.add(issuer)
    await session.flush()
    period = ReportingPeriod(
        issuer_id=issuer.id,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 12, 31),
        fiscal_year=2024,
        period_type="annual",
        consolidation_scope="consolidated",
    )
    source_id = (await session.execute(sa.select(DataSource.id).where(DataSource.code == "CVM"))).scalar_one()
    source = SourceObject(source_id=source_id, logical_uri=f"test://facts/{uuid4()}", object_type="json")
    session.add_all([period, source])
    await session.flush()
    version = SourceObjectVersion(
        source_object_id=source.id,
        version_number=1,
        content_sha256=uuid4().hex * 2,
        storage_key=f"test/facts/{uuid4()}",
        size_bytes=1,
        media_type="application/json",
        discovered_at=_dt(2024, 12, 31),
    )
    session.add(version)
    await session.flush()
    return {
        "issuer_id": issuer.id,
        "reporting_period_id": period.id,
        "taxonomy_account_id": None,
        "mapping_rule_id": None,
        "source_object_version_id": version.id,
    }


@pytest.mark.asyncio
async def test_revise_creates_fact(session: AsyncSession, fact_refs: dict) -> None:
    """First revise() creates revision 1 with no superseded fact."""
    repo = FinancialFactRepository(session)
    item = _make_input(**fact_refs)
    result = await repo.revise(item)
    assert result.created is True
    assert result.fact.revision_number == 1
    assert result.fact.valid_to is None
    assert result.superseded_fact_id is None
    await session.commit()


@pytest.mark.asyncio
async def test_revise_supersedes_existing(session: AsyncSession, fact_refs: dict) -> None:
    """Second revise() closes window on revision 1 and creates revision 2."""
    repo = FinancialFactRepository(session)
    item1 = _make_input(**fact_refs, knowledge_at=_dt(2025, 1, 2))
    await repo.revise(item1)
    await session.commit()

    item2 = _make_input(
        knowledge_at=_dt(2025, 6, 1),
        value=Decimal("6000.00"),
        **fact_refs,
    )
    result = await repo.revise(item2)
    assert result.created is True
    assert result.fact.revision_number == 2
    assert result.superseded_fact_id is not None
    assert result.fact.valid_from == _dt(2025, 6, 1)
    assert result.fact.valid_to is None
    await session.commit()


@pytest.mark.asyncio
async def test_list_as_of_filters_by_knowledge_at(session: AsyncSession, fact_refs: dict) -> None:
    """list_as_of before knowledge_at returns no facts."""
    repo = FinancialFactRepository(session)
    item = _make_input(**fact_refs, knowledge_at=_dt(2025, 3, 1))
    await repo.revise(item)
    await session.commit()

    results = await repo.list_as_of(
        item.issuer_id,
        item.reporting_period_id,
        _dt(2025, 1, 1),
    )
    assert len(results) == 0

    results_after = await repo.list_as_of(
        item.issuer_id,
        item.reporting_period_id,
        _dt(2025, 4, 1),
    )
    assert len(results_after) == 1


@pytest.mark.asyncio
async def test_idempotent_revise_returns_created_false(session: AsyncSession, fact_refs: dict) -> None:
    """Revise with identical data returns created=False."""
    repo = FinancialFactRepository(session)
    item = _make_input(**fact_refs)
    r1 = await repo.revise(item)
    await session.commit()

    r2 = await repo.revise(item)
    assert r2.created is False
    assert r2.fact.id == r1.fact.id
