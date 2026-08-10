from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from ia_investing.application.institutional_portfolio._nav import NavService
from ia_investing.domain.identity import InstitutionalAccessContext


def _context(organization_id: UUID | None = None) -> InstitutionalAccessContext:
    org = organization_id or uuid4()
    return InstitutionalAccessContext("manager", org, frozenset({uuid4()}), frozenset({"nav:publish"}), "paper")


def _mock_session() -> AsyncMock:
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.execute = AsyncMock(return_value=MagicMock())
    session.scalars = AsyncMock(return_value=MagicMock())
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    return session


def _mock_version(portfolio_id: UUID | None = None, mandate_id: UUID | None = None) -> MagicMock:
    v = MagicMock()
    v.id = uuid4()
    v.portfolio_id = portfolio_id or uuid4()
    v.mandate_id = mandate_id or uuid4()
    v.as_of = datetime(2026, 1, 1, tzinfo=UTC)
    v.status = "approved"
    return v


def _mock_portfolio(organization_id: UUID | None = None, owner_team_id: UUID | None = None) -> MagicMock:
    p = MagicMock()
    p.id = uuid4()
    p.organization_id = organization_id or uuid4()
    p.owner_team_id = owner_team_id or uuid4()
    p.base_currency = "BRL"
    return p


@pytest.mark.asyncio
async def test_resolve_portfolio_raises_when_version_not_found() -> None:
    session = _mock_session()
    session.get.return_value = None
    service = NavService(session)
    with pytest.raises(LookupError, match="portfolio version not found"):
        await service._resolve_portfolio(uuid4(), _context())


@pytest.mark.asyncio
async def test_list_nav_publications_delegates_to_session() -> None:
    session = _mock_session()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    session.scalars.return_value = mock_scalars
    service = NavService(session)
    portfolio_id = uuid4()
    result = await service.list_nav_publications(portfolio_id)
    assert result == []
    session.scalars.assert_called_once()


@pytest.mark.asyncio
async def test_list_nav_publications_filters_by_as_of() -> None:
    session = _mock_session()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    session.scalars.return_value = mock_scalars
    service = NavService(session)
    cutoff = datetime(2026, 6, 1, tzinfo=UTC)
    await service.list_nav_publications(uuid4(), as_of=cutoff)
    session.scalars.assert_called_once()


@pytest.mark.asyncio
async def test_resolve_portfolio_raises_when_portfolio_missing() -> None:
    session = _mock_session()
    version = _mock_version()
    portfolio = None

    async def fake_get(model, id_val, **kwargs):
        if model.__name__ == "InstitutionalPortfolioVersion":
            return version
        return portfolio

    session.get = fake_get
    service = NavService(session)
    with pytest.raises(RuntimeError, match="missing portfolio"):
        await service._resolve_portfolio(version.id, _context(version.portfolio_id))
