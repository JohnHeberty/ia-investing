"""Unit tests for RiskService — risk assessment, waivers, breaches."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
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
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    return session


def _mock_version(portfolio_id=None, mandate_id=None) -> MagicMock:
    v = MagicMock()
    v.id = uuid4()
    v.portfolio_id = portfolio_id or uuid4()
    v.mandate_id = mandate_id or uuid4()
    return v


def _mock_policy(mandate_id=None) -> MagicMock:
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


def _mock_portfolio(organization_id=None, owner_team_id=None) -> MagicMock:
    p = MagicMock()
    p.id = uuid4()
    p.organization_id = organization_id or uuid4()
    p.owner_team_id = owner_team_id or uuid4()
    return p


# ---------------------------------------------------------------------------
# assess_risk validation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestAssessRiskValidation:
    async def test_raises_when_version_not_found(self) -> None:
        session = _mock_session()
        session.get.return_value = None
        service = RiskService(session)
        with pytest.raises(LookupError, match="not found"):
            await service.assess_risk(uuid4(), uuid4(), datetime.now(UTC), _context())

    async def test_raises_when_policy_not_found(self) -> None:
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

    async def test_raises_when_mandate_mismatch(self) -> None:
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

    async def test_raises_when_naive_datetime(self) -> None:
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

    async def test_raises_when_no_positions(self) -> None:
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

    async def test_raises_when_price_age_zero(self) -> None:
        """max_price_age_hours=0 must be rejected."""
        session = _mock_session()
        mandate_id = uuid4()
        org_id = uuid4()
        team_id = uuid4()
        version = _mock_version(mandate_id=mandate_id)
        policy = _mock_policy(mandate_id=mandate_id)
        policy.limits["max_price_age_hours"] = 0
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
        pos = MagicMock()
        pos.instrument_id = uuid4()
        pos.quantity = Decimal("100")
        scalars_result = MagicMock()
        scalars_result.all.return_value = [pos]
        session.scalars.return_value = scalars_result

        service = RiskService(session)
        ctx = InstitutionalAccessContext("manager", org_id, frozenset({team_id}), frozenset({"risk:assess"}), "paper")
        with pytest.raises(ValueError, match="positive"):
            await service.assess_risk(version.id, policy.id, datetime.now(UTC), ctx)


# ---------------------------------------------------------------------------
# waive_breach
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestWaiveBreach:
    async def test_waive_breach_not_found(self) -> None:
        session = _mock_session()
        session.get.return_value = None
        service = RiskService(session)
        with pytest.raises(LookupError, match="not found"):
            await service.waive_breach(
                uuid4(), "test reason", datetime(2027, 1, 1, tzinfo=UTC), _context()
            )

    async def test_waive_breach_non_open_raises(self) -> None:
        session = _mock_session()
        ctx = _context()
        breach = MagicMock()
        breach.id = uuid4()
        breach.status = "waived"
        breach.risk_snapshot_id = uuid4()

        snapshot = MagicMock()
        snapshot.portfolio_version_id = uuid4()
        version = MagicMock()
        version.portfolio_id = uuid4()
        portfolio = _mock_portfolio(
            organization_id=ctx.organization_id,
            owner_team_id=next(iter(ctx.team_ids)),
        )

        async def fake_get(model, id_val, **kwargs):
            if model.__name__ == "RiskBreach":
                return breach
            if model.__name__ == "InstitutionalRiskSnapshot":
                return snapshot
            if model.__name__ == "InstitutionalPortfolioVersion":
                return version
            if model.__name__ == "ModelPortfolio":
                return portfolio
            return None

        session.get = fake_get
        service = RiskService(session)
        with pytest.raises(ValueError, match="only an open"):
            await service.waive_breach(
                breach.id, "reason", datetime(2027, 1, 1, tzinfo=UTC), ctx
            )

    async def test_waive_breach_empty_reason_raises(self) -> None:
        session = _mock_session()
        ctx = _context()
        breach = MagicMock()
        breach.id = uuid4()
        breach.status = "open"
        breach.risk_snapshot_id = uuid4()

        snapshot = MagicMock()
        snapshot.portfolio_version_id = uuid4()
        version = MagicMock()
        version.portfolio_id = uuid4()
        portfolio = _mock_portfolio(
            organization_id=ctx.organization_id,
            owner_team_id=next(iter(ctx.team_ids)),
        )

        async def fake_get(model, id_val, **kwargs):
            if model.__name__ == "RiskBreach":
                return breach
            if model.__name__ == "InstitutionalRiskSnapshot":
                return snapshot
            if model.__name__ == "InstitutionalPortfolioVersion":
                return version
            if model.__name__ == "ModelPortfolio":
                return portfolio
            return None

        session.get = fake_get
        service = RiskService(session)
        with pytest.raises(ValueError, match="reason is required"):
            await service.waive_breach(
                breach.id, "   ", datetime(2027, 1, 1, tzinfo=UTC), ctx
            )

    async def test_waive_breach_past_expiry_raises(self) -> None:
        session = _mock_session()
        ctx = _context()
        breach = MagicMock()
        breach.id = uuid4()
        breach.status = "open"
        breach.risk_snapshot_id = uuid4()

        snapshot = MagicMock()
        snapshot.portfolio_version_id = uuid4()
        version = MagicMock()
        version.portfolio_id = uuid4()
        portfolio = _mock_portfolio(
            organization_id=ctx.organization_id,
            owner_team_id=next(iter(ctx.team_ids)),
        )

        async def fake_get(model, id_val, **kwargs):
            if model.__name__ == "RiskBreach":
                return breach
            if model.__name__ == "InstitutionalRiskSnapshot":
                return snapshot
            if model.__name__ == "InstitutionalPortfolioVersion":
                return version
            if model.__name__ == "ModelPortfolio":
                return portfolio
            return None

        session.get = fake_get
        service = RiskService(session)
        with pytest.raises(ValueError, match="future timestamp"):
            await service.waive_breach(
                breach.id, "reason", datetime(2020, 1, 1, tzinfo=UTC), ctx
            )

    async def test_waive_breach_naive_expiry_raises(self) -> None:
        session = _mock_session()
        ctx = _context()
        breach = MagicMock()
        breach.id = uuid4()
        breach.status = "open"
        breach.risk_snapshot_id = uuid4()

        snapshot = MagicMock()
        snapshot.portfolio_version_id = uuid4()
        version = MagicMock()
        version.portfolio_id = uuid4()
        portfolio = _mock_portfolio(
            organization_id=ctx.organization_id,
            owner_team_id=next(iter(ctx.team_ids)),
        )

        async def fake_get(model, id_val, **kwargs):
            if model.__name__ == "RiskBreach":
                return breach
            if model.__name__ == "InstitutionalRiskSnapshot":
                return snapshot
            if model.__name__ == "InstitutionalPortfolioVersion":
                return version
            if model.__name__ == "ModelPortfolio":
                return portfolio
            return None

        session.get = fake_get
        service = RiskService(session)
        with pytest.raises(ValueError, match="aware future timestamp"):
            await service.waive_breach(
                breach.id, "reason", datetime(2027, 1, 1), ctx
            )

    async def test_waive_breach_requires_permission(self) -> None:
        session = _mock_session()
        breach = MagicMock()
        breach.id = uuid4()
        breach.status = "open"
        breach.risk_snapshot_id = uuid4()

        snapshot = MagicMock()
        snapshot.portfolio_version_id = uuid4()
        version = MagicMock()
        version.portfolio_id = uuid4()
        portfolio = _mock_portfolio(
            organization_id=_context().organization_id,
            owner_team_id=next(iter(_context().team_ids)),
        )

        async def fake_get(model, id_val, **kwargs):
            if model.__name__ == "RiskBreach":
                return breach
            if model.__name__ == "InstitutionalRiskSnapshot":
                return snapshot
            if model.__name__ == "InstitutionalPortfolioVersion":
                return version
            if model.__name__ == "ModelPortfolio":
                return portfolio
            return None

        session.get = fake_get
        service = RiskService(session)
        ctx_no_perm = InstitutionalAccessContext(
            "manager", portfolio.organization_id, frozenset({portfolio.owner_team_id}),
            frozenset({"risk:assess"}), "paper"
        )
        with pytest.raises(PermissionError, match="risk:waive"):
            await service.waive_breach(
                breach.id, "reason", datetime(2027, 6, 1, tzinfo=UTC), ctx_no_perm
            )


# ---------------------------------------------------------------------------
# list_risk_breaches
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestListRiskBreaches:
    async def test_returns_none_when_snapshot_missing(self) -> None:
        session = _mock_session()
        session.get.return_value = None
        service = RiskService(session)
        result = await service.list_risk_breaches(uuid4(), uuid4())
        assert result is None

    async def test_returns_none_when_version_missing(self) -> None:
        session = _mock_session()
        snapshot = MagicMock()
        snapshot.portfolio_version_id = uuid4()

        async def fake_get(model, id_val, **kwargs):
            if model.__name__ == "InstitutionalRiskSnapshot":
                return snapshot
            return None

        session.get = fake_get
        service = RiskService(session)
        result = await service.list_risk_breaches(snapshot.id, uuid4())
        assert result is None

    async def test_returns_none_when_org_mismatch(self) -> None:
        session = _mock_session()
        snapshot = MagicMock()
        snapshot.portfolio_version_id = uuid4()
        version = MagicMock()
        version.portfolio_id = uuid4()
        portfolio = _mock_portfolio(organization_id=uuid4())

        async def fake_get(model, id_val, **kwargs):
            if model.__name__ == "InstitutionalRiskSnapshot":
                return snapshot
            if model.__name__ == "InstitutionalPortfolioVersion":
                return version
            if model.__name__ == "ModelPortfolio":
                return portfolio
            return None

        session.get = fake_get
        service = RiskService(session)
        result = await service.list_risk_breaches(snapshot.id, uuid4())
        assert result is None

    async def test_returns_breaches(self) -> None:
        session = _mock_session()
        org_id = uuid4()
        snapshot = MagicMock()
        snapshot.portfolio_version_id = uuid4()
        version = MagicMock()
        version.portfolio_id = uuid4()
        portfolio = _mock_portfolio(organization_id=org_id)

        breach = MagicMock()

        async def fake_get(model, id_val, **kwargs):
            if model.__name__ == "InstitutionalRiskSnapshot":
                return snapshot
            if model.__name__ == "InstitutionalPortfolioVersion":
                return version
            if model.__name__ == "ModelPortfolio":
                return portfolio
            return None

        session.get = fake_get
        breach_scalars = MagicMock()
        breach_scalars.all.return_value = [breach]
        session.scalars.return_value = breach_scalars

        service = RiskService(session)
        result = await service.list_risk_breaches(snapshot.id, org_id)
        assert result is not None
        snap, breaches = result
        assert snap is snapshot
        assert len(breaches) == 1


# ---------------------------------------------------------------------------
# expire_waivers
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestExpireWaivers:
    async def test_expire_waivers_naive_raises(self) -> None:
        session = _mock_session()
        service = RiskService(session)
        with pytest.raises(ValueError, match="timezone-aware"):
            await service.expire_waivers(datetime(2026, 1, 1))

    async def test_expire_waivers_returns_count(self) -> None:
        session = _mock_session()
        mock_result = MagicMock()
        mock_result.rowcount = 3
        session.execute.return_value = mock_result
        service = RiskService(session)
        count = await service.expire_waivers(datetime.now(UTC))
        assert count == 3

    async def test_expire_waivers_zero_count(self) -> None:
        session = _mock_session()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        session.execute.return_value = mock_result
        service = RiskService(session)
        count = await service.expire_waivers(datetime.now(UTC))
        assert count == 0
