"""Integration test: instrument master resolve — ticker, CNPJ, name.

Tests InstrumentMasterService.resolve() against a real PostgreSQL:
  1. Insert Issuer + Instrument + Listing directly
  2. Resolve by ticker
  3. Resolve by issuer name
  4. Resolve by CNPJ
  5. Unresolvable query returns None
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.catalog import Issuer
from database.models.instrument_master import Instrument, Listing
from ia_investing.application.instruments import InstrumentMasterService


@pytest.fixture
def issuer_id():
    return uuid4()


@pytest.fixture
def instrument_id():
    return uuid4()


async def _seed_issuer(
    session: AsyncSession,
    *,
    issuer_id=None,
    name: str = "Petróleo Brasileiro S.A.",
    cnpj: str = "33000167000101",
):
    from database.models.catalog import Industry

    ind = (await session.execute(
        __import__("sqlalchemy").select(Industry).limit(1)
    )).scalar_one_or_none()
    if ind is None:
        ind = Industry(id=uuid4(), name_pt="Petróleo e Gás", sector="Energia", isic_code="06")
        session.add(ind)
        await session.flush()

    iid = issuer_id or uuid4()
    issuer = Issuer(id=iid, name_pt=name, cnpj=cnpj, industry_id=ind.id, is_active=True)
    session.add(issuer)
    await session.flush()
    return issuer


async def _seed_instrument(session: AsyncSession, issuer_id, *, instrument_id=None):
    iid = instrument_id or uuid4()
    inst = Instrument(id=iid, issuer_id=issuer_id, share_class="ON", is_active=True)
    session.add(inst)
    await session.flush()
    return inst


async def _seed_listing(session: AsyncSession, instrument_id, ticker: str = "PETR4"):
    listing = Listing(
        id=uuid4(),
        instrument_id=instrument_id,
        ticker=ticker,
        exchange_code="B3",
        market_segment="N1",
        valid_from=date(2020, 1, 1),
        valid_to=None,
    )
    session.add(listing)
    await session.flush()
    return listing


@pytest.mark.asyncio
async def test_resolve_by_ticker(session: AsyncSession) -> None:
    issuer = await _seed_issuer(session)
    inst = await _seed_instrument(session, issuer.id)
    await _seed_listing(session, inst.id, "PETR4")

    svc = InstrumentMasterService(session)
    result = await svc.resolve("PETR4", date(2025, 6, 1))
    assert result is not None
    assert result.resolution_type == "listing"
    assert result.ticker == "PETR4"
    assert result.issuer_name == "Petróleo Brasileiro S.A."


@pytest.mark.asyncio
async def test_resolve_by_name(session: AsyncSession) -> None:
    issuer = await _seed_issuer(session, name="VALE S.A.", cnpj="60872504000112")
    await _seed_instrument(session, issuer.id)

    svc = InstrumentMasterService(session)
    result = await svc.resolve("VALE S.A.", date(2025, 6, 1))
    assert result is not None
    assert result.resolution_type == "issuer"
    assert result.issuer_name == "VALE S.A."


@pytest.mark.asyncio
async def test_resolve_by_cnpj(session: AsyncSession) -> None:
    issuer = await _seed_issuer(session, name="Banco do Brasil", cnpj="00000000000191")
    await _seed_instrument(session, issuer.id)

    svc = InstrumentMasterService(session)
    result = await svc.resolve("00000000000191", date(2025, 6, 1))
    assert result is not None
    assert result.resolution_type == "issuer"
    assert result.issuer_name == "Banco do Brasil"


@pytest.mark.asyncio
async def test_resolve_returns_none_for_unknown(session: AsyncSession) -> None:
    svc = InstrumentMasterService(session)
    result = await svc.resolve("NÃOEXISTE99", date(2025, 6, 1))
    assert result is None
