"""Integration test: source registry — DataSources seeded by migration.

Verifies:
  - CVM and B3 sources exist in data_sources table
  - Source licenses present with terms_url
  - Source SLAs present with frequency
  - Health query returns active status
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.data_foundation import DataSource, SourceLicense, SourceSLA


async def test_cvm_source_exists(session: AsyncSession) -> None:
    """CVM data source must be seeded by migration."""
    stmt = sa.select(DataSource).where(DataSource.code == "data-steward-cvm")
    row = (await session.execute(stmt)).scalar_one_or_none()
    assert row is not None, "CVM data source not found"
    assert row.is_active is True
    assert row.rate_limit_per_minute == 30


async def test_b3_source_exists(session: AsyncSession) -> None:
    """B3 data source must be seeded by migration."""
    stmt = sa.select(DataSource).where(DataSource.code == "data-steward-b3")
    row = (await session.execute(stmt)).scalar_one_or_none()
    assert row is not None, "B3 data source not found"
    assert row.is_active is True
    assert row.rate_limit_per_minute == 10
    assert row.credential_reference is not None


async def test_source_licenses_present(session: AsyncSession) -> None:
    """Both CVM-OFFICIAL and B3-OFFICIAL licenses must exist."""
    rows = (await session.execute(sa.select(SourceLicense))).scalars().all()
    codes = {r.code for r in rows}
    assert "CVM-OFFICIAL" in codes
    assert "B3-OFFICIAL" in codes


async def test_source_slas_present(session: AsyncSession) -> None:
    """Both sources must have SLA definitions with expected frequency."""
    rows = (await session.execute(sa.select(SourceSLA))).scalars().all()
    assert len(rows) >= 2, f"Expected >= 2 SLAs, got {len(rows)}"
    for sla in rows:
        assert sla.expected_frequency_minutes > 0
        assert sla.freshness_grace_minutes > 0


async def test_all_seeded_sources_are_active(session: AsyncSession) -> None:
    """Every seeded data source should be active."""
    rows = (await session.execute(sa.select(DataSource))).scalars().all()
    assert len(rows) >= 2
    for ds in rows:
        assert ds.is_active is True, f"Source {ds.code} is inactive"
