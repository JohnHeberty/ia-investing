from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from ia_investing.application.institutional_portfolio._risk import RiskService
from ia_investing.domain.identity import InstitutionalAccessContext


def _context(org_id: UUID | None = None, team_id: UUID | None = None) -> InstitutionalAccessContext:
    org = org_id or uuid4()
    team = team_id or uuid4()
    return InstitutionalAccessContext(
        "manager", org, frozenset({team}), frozenset({"risk:assess", "risk:waive"}), "paper"
    )


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


def _mock_policy(mandate_id: UUID | None = None) -> MagicMock:
    p = MagicMock()
    p.id = uuid4()
    p.mandate_id = mandate_id or uuid4()
    p.content_sha256 = "abc123"
    p.limits = {
        "max_price_age_hours": 72,
        "limits": [
            {"name": "concentration_top5", "type": "hard", "maximum": 0.40},
        ],
    }
    return p


def _mock_portfolio(organization_id: UUID | None = None, owner_team_id: UUID | None = None) -> MagicMock:
    p = MagicMock()
    p.id = uuid4()
    p.organization_id = organization_id or uuid4()
    p.owner_team_id = owner_team_id or uuid4()
    p.base_currency = "BRL"
    return p


@pytest.mark.asyncio
async def test_assess_risk_raises_when_version_not_found() -> None:
    session = _mock_session()
    session.get.return_value = None
    service = RiskService(session)
    with pytest.raises(LookupError, match="not found"):
        await service.assess_risk(uuid4(), uuid4(), datetime.now(UTC), _context())


@pytest.mark.asyncio
async def test_assess_risk_raises_when_policy_not_found() -> None:
    session = _mock_session()
    version = _mock_version()

    async def fake_get(model, id_val, **kwargs):
        if model.__name__ == "InstitutionalPortfolioVersion":
            return version
        return None

    session.get = fake_get
    service = RiskService(session)
    with pytest.raises(LookupError, match="not found"):
        await service.assess_risk(version.id, uuid4(), datetime.now(UTC), _context())


@pytest.mark.asyncio
async def test_assess_risk_raises_when_mandate_mismatch() -> None:
    session = _mock_session()
    version = _mock_version(mandate_id=uuid4())
    policy = _mock_policy(mandate_id=uuid4())

    async def fake_get(model, id_val, **kwargs):
        if model.__name__ == "InstitutionalPortfolioVersion":
            return version
        if model.__name__ == "InstitutionalRiskPolicy":
            return policy
        return None

    session.get = fake_get
    service = RiskService(session)
    with pytest.raises(LookupError, match="not found"):
        await service.assess_risk(version.id, policy.id, datetime.now(UTC), _context())


@pytest.mark.asyncio
async def test_assess_risk_raises_when_naive_datetime() -> None:
    session = _mock_session()
    mandate_id = uuid4()
    org_id = uuid4()
    team_id = uuid4()
    version = _mock_version(mandate_id=mandate_id)
    policy = _mock_policy(mandate_id=mandate_id)
    portfolio = _mock_portfolio(org_id, team_id)

    async def fake_get(model, id_val, **kwargs):
        if model.__name__ == "InstitutionalPortfolioVersion":
            return version
        if model.__name__ == "InstitutionalRiskPolicy":
            return policy
        if model.__name__ == "ModelPortfolio":
            return portfolio
        return None

    session.get = fake_get
    service = RiskService(session)
    ctx = InstitutionalAccessContext("manager", org_id, frozenset({team_id}), frozenset({"risk:assess"}), "paper")
    with pytest.raises(ValueError, match="timezone"):
        await service.assess_risk(version.id, policy.id, datetime(2026, 1, 1), ctx)


@pytest.mark.asyncio
async def test_assess_risk_raises_when_no_positions() -> None:
    session = _mock_session()
    mandate_id = uuid4()
    org_id = uuid4()
    team_id = uuid4()
    version = _mock_version(mandate_id=mandate_id)
    policy = _mock_policy(mandate_id=mandate_id)
    portfolio = _mock_portfolio(org_id, team_id)

    async def fake_get(model, id_val, **kwargs):
        if model.__name__ == "InstitutionalPortfolioVersion":
            return version
        if model.__name__ == "InstitutionalRiskPolicy":
            return policy
        if model.__name__ == "ModelPortfolio":
            return portfolio
        return None

    session.get = fake_get
    empty_scalars = MagicMock()
    empty_scalars.all.return_value = []
    session.scalars.return_value = empty_scalars
    service = RiskService(session)
    ctx = InstitutionalAccessContext("manager", org_id, frozenset({team_id}), frozenset({"risk:assess"}), "paper")
    with pytest.raises(ValueError, match="no positions"):
        await service.assess_risk(version.id, policy.id, datetime.now(UTC), ctx)


@pytest.mark.asyncio
async def test_list_risk_breaches_returns_none_when_snapshot_missing() -> None:
    session = _mock_session()
    session.get.return_value = None
    service = RiskService(session)
    result = await service.list_risk_breaches(uuid4(), uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_waive_breach_raises_when_breach_not_found() -> None:
    session = _mock_session()
    session.get.return_value = None
    service = RiskService(session)
    with pytest.raises(LookupError, match="not found"):
        await service.waive_breach(
            uuid4(),
            "test reason",
            datetime(2027, 1, 1, tzinfo=UTC),
            _context(),
        )
