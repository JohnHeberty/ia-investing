"""Unit tests for IntentService (paper_execution/_intent.py)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database.models.paper_execution import PaperOrder, TradeIntent
from database.models.portfolio_domain import InstitutionalPortfolioVersion, ModelPortfolio, StrategyMandate
from ia_investing.application.paper_execution._intent import IntentService
from ia_investing.domain.identity import InstitutionalAccessContext


_SHARED_TEAM = uuid4()


def _ctx(
    *,
    subject: str = "pm-1",
    org_id: UUID | None = None,
    team_ids: frozenset[UUID] | None = None,
    perms: frozenset[str] | None = None,
) -> InstitutionalAccessContext:
    org = org_id or uuid4()
    return InstitutionalAccessContext(
        subject=subject,
        organization_id=org,
        team_ids=team_ids or frozenset({_SHARED_TEAM}),
        permissions=perms or frozenset({"portfolio:propose", "portfolio:approve", "paper_orders:operate"}),
        environment="paper",
    )


def _version(*, status: str = "approved", as_of: datetime | None = None) -> InstitutionalPortfolioVersion:
    v = MagicMock(spec=InstitutionalPortfolioVersion)
    v.id = uuid4()
    v.status = status
    v.as_of = as_of or datetime(2026, 1, 1, tzinfo=UTC)
    v.portfolio_id = uuid4()
    return v


def _portfolio(*, org_id: UUID | None = None, team_id: UUID | None = None) -> ModelPortfolio:
    p = MagicMock(spec=ModelPortfolio)
    p.id = uuid4()
    p.organization_id = org_id or uuid4()
    p.owner_team_id = team_id or _SHARED_TEAM
    p.environment = "paper"
    p.mandate_id = uuid4()
    return p


def _mandate(*, instrument_ids: list | None = None) -> StrategyMandate:
    m = MagicMock(spec=StrategyMandate)
    m.id = uuid4()
    m.config = {"universe_definition": {"instrument_ids": instrument_ids or []}}
    return m


def _intent(*, org_id: UUID, status: str = "pending_approval", created_by: str = "pm-1") -> TradeIntent:
    i = MagicMock(spec=TradeIntent)
    i.id = uuid4()
    i.organization_id = org_id
    i.status = status
    i.created_by = created_by
    i.portfolio_version_id = uuid4()
    i.instrument_id = uuid4()
    i.side = "buy"
    i.quantity = Decimal("100")
    i.order_type = "market"
    i.limit_price = None
    return i


@pytest.mark.unit
class TestCreateIntent:
    @pytest.mark.asyncio
    @patch("ia_investing.application.paper_execution._intent.record", new_callable=AsyncMock)
    async def test_create_intent_success(self, mock_record: AsyncMock) -> None:
        session = AsyncMock()
        ctx = _ctx()
        ver = _version()
        port = _portfolio(org_id=ctx.organization_id)
        mandate = _mandate()

        session.get = AsyncMock(side_effect=[ver, port, mandate])
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        session.scalar = AsyncMock(return_value=0)
        session.flush = AsyncMock()

        svc = IntentService(session)
        corr = uuid4()
        now = datetime.now(UTC)
        intent, created = await svc.create_intent(
            portfolio_version_id=ver.id,
            instrument_id=uuid4(),
            idempotency_key="key-1",
            side="buy",
            quantity=Decimal("100"),
            order_type="market",
            limit_price=None,
            earliest_execution_at=now + timedelta(hours=1),
            expires_at=now + timedelta(hours=2),
            reason="test",
            context=ctx,
            correlation_id=corr,
        )
        assert created is True
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_intent_rejects_unapproved_version(self) -> None:
        session = AsyncMock()
        ctx = _ctx()
        ver = _version(status="draft")
        session.get = AsyncMock(return_value=ver)

        svc = IntentService(session)
        with pytest.raises(ValueError, match="approved portfolio version"):
            await svc.create_intent(
                portfolio_version_id=ver.id,
                instrument_id=uuid4(),
                idempotency_key="k",
                side="buy",
                quantity=Decimal("10"),
                order_type="market",
                limit_price=None,
                earliest_execution_at=datetime.now(UTC) + timedelta(hours=1),
                expires_at=datetime.now(UTC) + timedelta(hours=2),
                reason="r",
                context=ctx,
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_create_intent_missing_portfolio(self) -> None:
        session = AsyncMock()
        ctx = _ctx()
        ver = _version()
        session.get = AsyncMock(side_effect=[ver, None])

        svc = IntentService(session)
        with pytest.raises(LookupError, match="portfolio not found"):
            await svc.create_intent(
                portfolio_version_id=ver.id,
                instrument_id=uuid4(),
                idempotency_key="k",
                side="buy",
                quantity=Decimal("10"),
                order_type="market",
                limit_price=None,
                earliest_execution_at=datetime.now(UTC) + timedelta(hours=1),
                expires_at=datetime.now(UTC) + timedelta(hours=2),
                reason="r",
                context=ctx,
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_create_intent_naive_datetime_rejected(self) -> None:
        session = AsyncMock()
        ctx = _ctx()
        ver = _version()
        port = _portfolio(org_id=ctx.organization_id)
        mandate = _mandate()
        session.get = AsyncMock(side_effect=[ver, port, mandate])

        svc = IntentService(session)
        with pytest.raises(ValueError, match="timezone"):
            await svc.create_intent(
                portfolio_version_id=ver.id,
                instrument_id=uuid4(),
                idempotency_key="k",
                side="buy",
                quantity=Decimal("10"),
                order_type="market",
                limit_price=None,
                earliest_execution_at=datetime(2026, 6, 1),
                expires_at=datetime(2026, 6, 2),
                reason="r",
                context=ctx,
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_create_intent_execution_before_version_as_of(self) -> None:
        session = AsyncMock()
        ctx = _ctx()
        ver = _version(as_of=datetime(2026, 6, 1, tzinfo=UTC))
        port = _portfolio(org_id=ctx.organization_id)
        mandate = _mandate()
        session.get = AsyncMock(side_effect=[ver, port, mandate])

        svc = IntentService(session)
        with pytest.raises(ValueError, match="execution cannot precede"):
            await svc.create_intent(
                portfolio_version_id=ver.id,
                instrument_id=uuid4(),
                idempotency_key="k",
                side="buy",
                quantity=Decimal("10"),
                order_type="market",
                limit_price=None,
                earliest_execution_at=datetime(2026, 5, 1, tzinfo=UTC),
                expires_at=datetime(2026, 6, 2, tzinfo=UTC),
                reason="r",
                context=ctx,
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_create_intent_instrument_outside_universe(self) -> None:
        session = AsyncMock()
        ctx = _ctx()
        ver = _version()
        port = _portfolio(org_id=ctx.organization_id)
        mandate = _mandate(instrument_ids=[uuid4(), uuid4()])
        session.get = AsyncMock(side_effect=[ver, port, mandate])

        svc = IntentService(session)
        with pytest.raises(ValueError, match="outside the mandate universe"):
            await svc.create_intent(
                portfolio_version_id=ver.id,
                instrument_id=uuid4(),
                idempotency_key="k",
                side="buy",
                quantity=Decimal("10"),
                order_type="market",
                limit_price=None,
                earliest_execution_at=datetime.now(UTC) + timedelta(hours=1),
                expires_at=datetime.now(UTC) + timedelta(hours=2),
                reason="r",
                context=ctx,
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_create_intent_idempotent_returns_existing(self) -> None:
        session = AsyncMock()
        ctx = _ctx()
        ver = _version()
        port = _portfolio(org_id=ctx.organization_id)
        mandate = _mandate()
        existing = _intent(org_id=ctx.organization_id)

        session.get = AsyncMock(side_effect=[ver, port, mandate])
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing)))
        session.scalar = AsyncMock(return_value=0)

        svc = IntentService(session)
        intent, created = await svc.create_intent(
            portfolio_version_id=existing.portfolio_version_id,
            instrument_id=existing.instrument_id,
            idempotency_key="key-1",
            side=existing.side,
            quantity=existing.quantity,
            order_type=existing.order_type,
            limit_price=existing.limit_price,
            earliest_execution_at=datetime.now(UTC) + timedelta(hours=1),
            expires_at=datetime.now(UTC) + timedelta(hours=2),
            reason="r",
            context=ctx,
            correlation_id=uuid4(),
        )
        assert created is False
        assert intent.id == existing.id

    @pytest.mark.asyncio
    async def test_create_intent_idempotency_mismatch_rejected(self) -> None:
        session = AsyncMock()
        ctx = _ctx()
        ver = _version()
        port = _portfolio(org_id=ctx.organization_id)
        mandate = _mandate()
        existing = _intent(org_id=ctx.organization_id)

        session.get = AsyncMock(side_effect=[ver, port, mandate])
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing)))
        session.scalar = AsyncMock(return_value=0)

        svc = IntentService(session)
        with pytest.raises(ValueError, match="different paper intent"):
            await svc.create_intent(
                portfolio_version_id=uuid4(),
                instrument_id=uuid4(),
                idempotency_key="key-1",
                side="sell",
                quantity=Decimal("999"),
                order_type="limit",
                limit_price=Decimal("50"),
                earliest_execution_at=datetime.now(UTC) + timedelta(hours=1),
                expires_at=datetime.now(UTC) + timedelta(hours=2),
                reason="r",
                context=ctx,
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_create_intent_permission_denied(self) -> None:
        session = AsyncMock()
        ctx = _ctx(perms=frozenset())
        ver = _version()
        port = _portfolio(org_id=ctx.organization_id)
        mandate = _mandate()
        session.get = AsyncMock(side_effect=[ver, port, mandate])

        svc = IntentService(session)
        with pytest.raises(PermissionError):
            await svc.create_intent(
                portfolio_version_id=ver.id,
                instrument_id=uuid4(),
                idempotency_key="k",
                side="buy",
                quantity=Decimal("10"),
                order_type="market",
                limit_price=None,
                earliest_execution_at=datetime.now(UTC) + timedelta(hours=1),
                expires_at=datetime.now(UTC) + timedelta(hours=2),
                reason="r",
                context=ctx,
                correlation_id=uuid4(),
            )


@pytest.mark.unit
class TestDecideIntent:
    @pytest.mark.asyncio
    async def test_approve_intent(self) -> None:
        session = AsyncMock()
        ctx = _ctx()
        intent = _intent(org_id=ctx.organization_id, created_by="other-user")
        session.get = AsyncMock(return_value=intent)
        session.flush = AsyncMock()

        svc = IntentService(session)
        result = await svc.decide_intent(
            intent.id,
            approved=True,
            rationale="looks good",
            context=ctx,
            correlation_id=uuid4(),
        )
        assert result.status == "approved"
        assert result.approved_by == ctx.subject

    @pytest.mark.asyncio
    async def test_reject_intent(self) -> None:
        session = AsyncMock()
        ctx = _ctx()
        intent = _intent(org_id=ctx.organization_id, created_by="other-user")
        session.get = AsyncMock(return_value=intent)
        session.flush = AsyncMock()

        svc = IntentService(session)
        result = await svc.decide_intent(
            intent.id,
            approved=False,
            rationale="bad idea",
            context=ctx,
            correlation_id=uuid4(),
        )
        assert result.status == "cancelled"
        assert result.approved_by is None

    @pytest.mark.asyncio
    async def test_decide_intent_not_found(self) -> None:
        session = AsyncMock()
        ctx = _ctx()
        session.get = AsyncMock(return_value=None)

        svc = IntentService(session)
        with pytest.raises(LookupError, match="not found"):
            await svc.decide_intent(
                uuid4(),
                approved=True,
                rationale="ok",
                context=ctx,
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_decide_intent_wrong_org(self) -> None:
        session = AsyncMock()
        ctx = _ctx()
        intent = _intent(org_id=uuid4())
        session.get = AsyncMock(return_value=intent)

        svc = IntentService(session)
        with pytest.raises(LookupError, match="not found"):
            await svc.decide_intent(
                intent.id,
                approved=True,
                rationale="ok",
                context=ctx,
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_four_eyes_rejection(self) -> None:
        session = AsyncMock()
        ctx = _ctx(subject="pm-1")
        intent = _intent(org_id=ctx.organization_id, created_by="pm-1")
        session.get = AsyncMock(return_value=intent)

        svc = IntentService(session)
        with pytest.raises(PermissionError, match="author cannot approve"):
            await svc.decide_intent(
                intent.id,
                approved=True,
                rationale="self-approve",
                context=ctx,
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_invalid_transition_rejected(self) -> None:
        session = AsyncMock()
        ctx = _ctx()
        intent = _intent(org_id=ctx.organization_id, status="completed", created_by="other")
        session.get = AsyncMock(return_value=intent)

        svc = IntentService(session)
        with pytest.raises(ValueError, match="invalid"):
            await svc.decide_intent(
                intent.id,
                approved=True,
                rationale="r",
                context=ctx,
                correlation_id=uuid4(),
            )


@pytest.mark.unit
class TestCancelIntent:
    @pytest.mark.asyncio
    async def test_cancel_intent_success(self) -> None:
        session = AsyncMock()
        ctx = _ctx()
        intent = _intent(org_id=ctx.organization_id)
        session.get = AsyncMock(return_value=intent)
        session.scalar = AsyncMock(return_value=None)
        session.flush = AsyncMock()

        svc = IntentService(session)
        result = await svc.cancel_intent(
            intent.id,
            reason="no longer needed",
            context=ctx,
            correlation_id=uuid4(),
        )
        assert result.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_intent_not_found(self) -> None:
        session = AsyncMock()
        ctx = _ctx()
        session.get = AsyncMock(return_value=None)

        svc = IntentService(session)
        with pytest.raises(LookupError, match="not found"):
            await svc.cancel_intent(
                uuid4(),
                reason="r",
                context=ctx,
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_cancel_intent_cancels_linked_order(self) -> None:
        session = AsyncMock()
        ctx = _ctx()
        intent = _intent(org_id=ctx.organization_id)
        order = MagicMock(spec=PaperOrder)
        order.id = uuid4()
        order.status = "accepted"

        session.get = AsyncMock(return_value=intent)
        session.scalar = AsyncMock(return_value=order)
        session.flush = AsyncMock()

        svc = IntentService(session)
        result = await svc.cancel_intent(
            intent.id,
            reason="cancel all",
            context=ctx,
            correlation_id=uuid4(),
        )
        assert result.status == "cancelled"
        assert order.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_intent_skips_terminal_order(self) -> None:
        session = AsyncMock()
        ctx = _ctx()
        intent = _intent(org_id=ctx.organization_id)
        order = MagicMock(spec=PaperOrder)
        order.id = uuid4()
        order.status = "filled"

        session.get = AsyncMock(return_value=intent)
        session.scalar = AsyncMock(return_value=order)
        session.flush = AsyncMock()

        svc = IntentService(session)
        result = await svc.cancel_intent(
            intent.id,
            reason="r",
            context=ctx,
            correlation_id=uuid4(),
        )
        assert result.status == "cancelled"
        assert order.status == "filled"

    @pytest.mark.asyncio
    async def test_cancel_already_cancelled_fails(self) -> None:
        session = AsyncMock()
        ctx = _ctx()
        intent = _intent(org_id=ctx.organization_id, status="cancelled")
        session.get = AsyncMock(return_value=intent)

        svc = IntentService(session)
        with pytest.raises(ValueError, match="invalid"):
            await svc.cancel_intent(
                intent.id,
                reason="r",
                context=ctx,
                correlation_id=uuid4(),
            )


@pytest.mark.unit
class TestListTradeIntents:
    @pytest.mark.asyncio
    async def test_list_returns_intents(self) -> None:
        session = AsyncMock()
        org = uuid4()
        i1 = _intent(org_id=org)
        i2 = _intent(org_id=org)
        result_mock = MagicMock()
        result_mock.all.return_value = [i1, i2]
        session.scalars = AsyncMock(return_value=result_mock)

        svc = IntentService(session)
        intents = await svc.list_trade_intents(org)
        assert len(intents) == 2

    @pytest.mark.asyncio
    async def test_list_empty(self) -> None:
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.all.return_value = []
        session.scalars = AsyncMock(return_value=result_mock)

        svc = IntentService(session)
        intents = await svc.list_trade_intents(uuid4())
        assert intents == []
