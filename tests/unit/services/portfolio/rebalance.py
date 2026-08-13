"""Unit tests for RebalanceService — org scoping, propose, approve, execute, drift, compliance."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from ia_investing.application.rebalance_service import (
    MAX_CONCENTRATION_PCT,
    MAX_SECTOR_PCT,
    MIN_TRADE_SIZE_PCT,
    RebalanceService,
)



_SENTINEL = object()


@pytest.fixture()
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    return session


@pytest.fixture()
def org_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def portfolio_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def service(mock_session: AsyncMock, org_id: uuid.UUID) -> RebalanceService:
    return RebalanceService(mock_session, organization_id=org_id)


def _make_portfolio_model(**overrides: object) -> MagicMock:
    p = MagicMock()
    p.id = overrides.get("id", uuid.uuid4())
    p.name = overrides.get("name", "Model Portfolio")
    p.state = overrides.get("state", "active")
    return p


def _make_position(**overrides: object) -> MagicMock:
    p = MagicMock()
    p.id = overrides.get("id", uuid.uuid4())
    p.portfolio_id = overrides.get("portfolio_id", uuid.uuid4())
    p.ticker_symbol = overrides.get("ticker_symbol", "PETR4")
    p.quantity = Decimal(str(overrides.get("quantity", 100)))
    p.current_price = Decimal(str(overrides.get("current_price", 25.0)))
    p.weight_pct = Decimal(str(overrides.get("weight_pct", 0.10)))
    return p


def _make_proposal(**overrides: object) -> MagicMock:
    p = MagicMock()
    p.id = overrides.get("id", uuid.uuid4())
    p.portfolio_id = overrides.get("portfolio_id", uuid.uuid4())
    p.status = overrides.get("status", "draft")
    p.target_allocations = overrides.get("target_allocations", {"PETR4": 0.20})
    p.current_allocations = overrides.get("current_allocations", {"PETR4": 0.10})
    p.drift_analysis = overrides.get("drift_analysis", {"max_drift": 0.10, "total_drift": 0.10, "items": []})
    p.rationale = overrides.get("rationale", "Rebalance for Q2")
    p.created_by = overrides.get("created_by", "user@test.com")
    p.approved_by = overrides.get("approved_by", None)
    p.approval_notes = overrides.get("approval_notes", None)
    p.cancelled_reason = overrides.get("cancelled_reason", None)
    p.created_at = overrides.get("created_at", datetime.now(UTC))
    p.updated_at = overrides.get("updated_at", datetime.now(UTC))
    p.completed_at = overrides.get("completed_at", None)
    p.cancelled_at = overrides.get("cancelled_at", None)
    return p


def _exec(scalar_one=_SENTINEL, scalars_all=_SENTINEL) -> MagicMock:
    """Build a mock for session.execute() result."""
    r = MagicMock()
    r.scalar_one_or_none.return_value = None if scalar_one is _SENTINEL else scalar_one
    if scalars_all is not _SENTINEL:
        r.scalars.return_value.all.return_value = scalars_all
    return r


def _setup_proposal_dict(mock_session: AsyncMock, proposal: MagicMock) -> None:
    """Set up mock_session.execute side_effect for _proposal_to_dict (2 calls after the initial _get_proposal)."""
    mock_session.execute.side_effect = [
        _exec(scalar_one=proposal),           # _get_proposal
        _exec(scalar_one=proposal),           # _proposal_to_dict: _get_proposal
        _exec(scalars_all=[]),                # _proposal_to_dict: trades query
    ]


def _setup_portfolio_nav(
    mock_session: AsyncMock,
    model: MagicMock,
    positions: list | None = None,
    nav_rows: list | None = None,
) -> None:
    """Set up mock for _get_portfolio (2 calls) + _get_positions (1 call)."""
    if positions is None:
        positions = []
    if nav_rows is None:
        nav_rows = [(Decimal("100"), Decimal("10000"))]
    mock_session.execute.side_effect = [
        _exec(scalar_one=model),          # _get_portfolio: ModelPortfolio query
        _exec(scalars_all=nav_rows),       # _get_portfolio: NAV query
        _exec(scalars_all=positions),      # _get_positions query
    ]


# ---------------------------------------------------------------------------
# Organization scoping
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestOrganizationScoping:
    async def test_get_portfolio_filters_by_org(self, mock_session, org_id, portfolio_id):
        svc = RebalanceService(mock_session, organization_id=org_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(LookupError, match="not found"):
            await svc._get_portfolio(portfolio_id)

    async def test_get_positions_filters_by_org(self, mock_session, org_id, portfolio_id):
        svc = RebalanceService(mock_session, organization_id=org_id)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await svc._get_positions(portfolio_id)

        call_args = mock_session.execute.call_args[0][0]
        query_str = str(call_args)
        assert "organization_id" in query_str

    async def test_list_proposals_filters_by_org(self, mock_session, org_id):
        svc = RebalanceService(mock_session, organization_id=org_id)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await svc.list_proposals()

        call_args = mock_session.execute.call_args[0][0]
        query_str = str(call_args)
        assert "organization_id" in query_str

    async def test_no_org_filter_when_none(self, mock_session, portfolio_id):
        svc = RebalanceService(mock_session, organization_id=None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(LookupError):
            await svc._get_portfolio(portfolio_id)


# ---------------------------------------------------------------------------
# Drift calculations
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestComputeDriftV2:
    def test_empty_drift(self) -> None:
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._compute_drift({}, {})
        assert result["max_drift"] == 0.0
        assert result["total_drift"] == 0.0
        assert result["items"] == []

    def test_single_ticker_green(self) -> None:
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._compute_drift({"PETR4": 0.10}, {"PETR4": 0.105})
        assert result["items"][0]["severity"] == "green"

    def test_single_ticker_yellow(self) -> None:
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._compute_drift({"PETR4": 0.10}, {"PETR4": 0.12})
        assert result["items"][0]["severity"] == "yellow"

    def test_single_ticker_red(self) -> None:
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._compute_drift({"PETR4": 0.10}, {"PETR4": 0.15})
        assert result["items"][0]["severity"] == "red"

    def test_max_drift_is_largest(self) -> None:
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._compute_drift({"A": 0.10, "B": 0.30}, {"A": 0.15, "B": 0.32})
        assert result["max_drift"] == 0.05
        assert result["total_drift"] == pytest.approx(0.07)

    def test_new_ticker_in_target(self) -> None:
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._compute_drift({}, {"PETR4": 0.20})
        assert result["items"][0]["ticker"] == "PETR4"
        assert result["max_drift"] == 0.20

    def test_ticker_removed_in_target(self) -> None:
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._compute_drift({"PETR4": 0.15}, {})
        assert result["items"][0]["ticker"] == "PETR4"
        assert result["items"][0]["drift"] == 0.15

    def test_sorted_by_drift_descending(self) -> None:
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._compute_drift({"A": 0.10, "B": 0.20, "C": 0.30}, {"A": 0.12, "B": 0.18, "C": 0.35})
        drifts = [item["drift"] for item in result["items"]]
        assert drifts == sorted(drifts, reverse=True)


# ---------------------------------------------------------------------------
# Compliance checks
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestComplianceV2:
    def test_all_pass(self) -> None:
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._check_compliance({"PETR4": 0.10, "VALE3": 0.15})
        assert result["passed"] is True
        assert result["issues"] == []

    def test_concentration_breach(self) -> None:
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._check_compliance({"PETR4": 0.30})
        assert result["passed"] is False
        assert "PETR4" in result["issues"][0]

    def test_exact_limit_passes(self) -> None:
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._check_compliance({"PETR4": float(MAX_CONCENTRATION_PCT)})
        assert result["passed"] is True

    def test_multiple_breaches(self) -> None:
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._check_compliance({"A": 0.30, "B": 0.30})
        assert len(result["issues"]) == 2

    def test_limits_in_output(self) -> None:
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._check_compliance({})
        assert result["concentration_limit"] == float(MAX_CONCENTRATION_PCT)
        assert result["sector_limit"] == float(MAX_SECTOR_PCT)


# ---------------------------------------------------------------------------
# Propose rebalance
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestProposeRebalance:
    async def test_propose_creates_draft(
        self, mock_session: AsyncMock, portfolio_id: uuid.UUID
    ) -> None:
        svc = RebalanceService(mock_session)
        model = _make_portfolio_model(id=portfolio_id)
        proposal = _make_proposal(rationale="Q2 rebalance")

        # _get_positions (1) + _get_portfolio (2) + _get_positions (1) + _proposal_to_dict (2) = 6
        mock_session.execute.side_effect = [
            _exec(scalars_all=[]),              # propose_rebalance: _get_positions
            _exec(scalar_one=model),             # calculate_rebalance: _get_portfolio
            _exec(scalars_all=[]),               # calculate_rebalance: _get_portfolio nav
            _exec(scalars_all=[]),               # calculate_rebalance: _get_positions
            _exec(scalar_one=proposal),          # _proposal_to_dict: _get_proposal
            _exec(scalars_all=[]),               # _proposal_to_dict: trades query
        ]

        result = await svc.propose_rebalance(
            portfolio_id,
            {"PETR4": 0.20, "VALE3": 0.30},
            rationale="Q2 rebalance",
            created_by="user@test.com",
        )
        assert result["status"] == "draft"
        assert result["rationale"] == "Q2 rebalance"
        assert mock_session.add.call_count >= 1

    async def test_propose_computes_drift(
        self, mock_session: AsyncMock, portfolio_id: uuid.UUID
    ) -> None:
        svc = RebalanceService(mock_session)
        model = _make_portfolio_model(id=portfolio_id)
        pos = _make_position(portfolio_id=portfolio_id, ticker_symbol="PETR4", weight_pct=0.10)
        proposal = _make_proposal(
            drift_analysis={
                "max_drift": 0.20, "total_drift": 0.20, "items": [],
                "compliance": {"passed": True, "issues": [], "concentration_limit": 0.25, "sector_limit": 0.40},
            }
        )

        mock_session.execute.side_effect = [
            _exec(scalars_all=[pos]),            # propose_rebalance: _get_positions
            _exec(scalar_one=model),             # calculate_rebalance: _get_portfolio
            _exec(scalars_all=[(Decimal("100"), Decimal("10000"))]),  # nav
            _exec(scalars_all=[pos]),            # calculate_rebalance: _get_positions
            _exec(scalar_one=proposal),          # _proposal_to_dict: _get_proposal
            _exec(scalars_all=[]),               # _proposal_to_dict: trades
        ]

        result = await svc.propose_rebalance(
            portfolio_id, {"PETR4": 0.30}, rationale="test", created_by="u"
        )
        assert "drift_analysis" in result
        assert "compliance" in result["drift_analysis"]


# ---------------------------------------------------------------------------
# Approve rebalance
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestApproveRebalance:
    async def test_approve_draft(self, mock_session: AsyncMock) -> None:
        svc = RebalanceService(mock_session)
        proposal = _make_proposal(status="draft")
        _setup_proposal_dict(mock_session, proposal)

        result = await svc.approve_rebalance(proposal.id, "approver@test.com", notes="LGTM")
        assert proposal.status == "approved"
        assert proposal.approved_by == "approver@test.com"
        assert proposal.approval_notes == "LGTM"

    async def test_approve_non_draft_raises(self, mock_session: AsyncMock) -> None:
        svc = RebalanceService(mock_session)
        proposal = _make_proposal(status="approved")
        mock_session.execute.return_value = _exec(scalar_one=proposal)

        with pytest.raises(ValueError, match="Cannot approve"):
            await svc.approve_rebalance(proposal.id, "user")

    async def test_approve_not_found(self, mock_session: AsyncMock) -> None:
        svc = RebalanceService(mock_session)
        mock_session.execute.return_value = _exec(scalar_one=None)

        with pytest.raises(LookupError, match="not found"):
            await svc.approve_rebalance(uuid.uuid4(), "user")


# ---------------------------------------------------------------------------
# Execute rebalance step
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestExecuteRebalanceStep:
    async def test_execute_transitions_to_in_progress(
        self, mock_session: AsyncMock
    ) -> None:
        svc = RebalanceService(mock_session)
        proposal = _make_proposal(status="approved")
        trade = MagicMock()
        trade.id = uuid.uuid4()
        trade.status = "pending"

        # _get_proposal (1) + trades query (1) + _proposal_to_dict (2) = 4
        mock_session.execute.side_effect = [
            _exec(scalar_one=proposal),          # _get_proposal
            _exec(scalars_all=[trade]),           # trades query
            _exec(scalar_one=proposal),           # _proposal_to_dict: _get_proposal
            _exec(scalars_all=[]),                # _proposal_to_dict: trades
        ]

        result = await svc.execute_rebalance_step(proposal.id, [trade.id])
        assert proposal.status == "in_progress"
        assert trade.status == "executed"

    async def test_execute_rejects_draft(self, mock_session: AsyncMock) -> None:
        svc = RebalanceService(mock_session)
        proposal = _make_proposal(status="draft")
        mock_session.execute.return_value = _exec(scalar_one=proposal)

        with pytest.raises(ValueError, match="Cannot execute"):
            await svc.execute_rebalance_step(proposal.id, [uuid.uuid4()])


# ---------------------------------------------------------------------------
# Complete rebalance
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestCompleteRebalance:
    async def test_complete_approved(self, mock_session: AsyncMock) -> None:
        svc = RebalanceService(mock_session)
        proposal = _make_proposal(status="approved")
        _setup_proposal_dict(mock_session, proposal)

        result = await svc.complete_rebalance(proposal.id)
        assert proposal.status == "completed"
        assert proposal.completed_at is not None

    async def test_complete_in_progress(self, mock_session: AsyncMock) -> None:
        svc = RebalanceService(mock_session)
        proposal = _make_proposal(status="in_progress")
        _setup_proposal_dict(mock_session, proposal)

        result = await svc.complete_rebalance(proposal.id)
        assert proposal.status == "completed"

    async def test_complete_draft_raises(self, mock_session: AsyncMock) -> None:
        svc = RebalanceService(mock_session)
        proposal = _make_proposal(status="draft")
        mock_session.execute.return_value = _exec(scalar_one=proposal)

        with pytest.raises(ValueError, match="Cannot complete"):
            await svc.complete_rebalance(proposal.id)

    async def test_complete_cancelled_raises(self, mock_session: AsyncMock) -> None:
        svc = RebalanceService(mock_session)
        proposal = _make_proposal(status="cancelled")
        mock_session.execute.return_value = _exec(scalar_one=proposal)

        with pytest.raises(ValueError, match="Cannot complete"):
            await svc.complete_rebalance(proposal.id)


# ---------------------------------------------------------------------------
# Cancel rebalance
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestCancelRebalance:
    async def test_cancel_draft(self, mock_session: AsyncMock) -> None:
        svc = RebalanceService(mock_session)
        proposal = _make_proposal(status="draft")
        _setup_proposal_dict(mock_session, proposal)

        result = await svc.cancel_rebalance(proposal.id, "Market conditions changed")
        assert proposal.status == "cancelled"
        assert proposal.cancelled_reason == "Market conditions changed"
        assert proposal.cancelled_at is not None

    async def test_cancel_completed_raises(self, mock_session: AsyncMock) -> None:
        svc = RebalanceService(mock_session)
        proposal = _make_proposal(status="completed")
        mock_session.execute.return_value = _exec(scalar_one=proposal)

        with pytest.raises(ValueError, match="Cannot cancel"):
            await svc.cancel_rebalance(proposal.id, "reason")

    async def test_cancel_already_cancelled_raises(self, mock_session: AsyncMock) -> None:
        svc = RebalanceService(mock_session)
        proposal = _make_proposal(status="cancelled")
        mock_session.execute.return_value = _exec(scalar_one=proposal)

        with pytest.raises(ValueError, match="Cannot cancel"):
            await svc.cancel_rebalance(proposal.id, "reason")


# ---------------------------------------------------------------------------
# Get rebalance status
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestGetRebalanceStatus:
    async def test_status_with_trades(self, mock_session: AsyncMock) -> None:
        svc = RebalanceService(mock_session)
        proposal = _make_proposal(status="in_progress")

        trade1 = MagicMock()
        trade1.status = "executed"
        trade2 = MagicMock()
        trade2.status = "skipped"
        trade3 = MagicMock()
        trade3.status = "failed"

        mock_session.execute.side_effect = [
            _exec(scalar_one=proposal),           # _get_proposal
            _exec(scalars_all=[trade1, trade2, trade3]),  # trades query
            _exec(scalar_one=proposal),            # _proposal_to_dict: _get_proposal
            _exec(scalars_all=[]),                 # _proposal_to_dict: trades
        ]

        result = await svc.get_rebalance_status(proposal.id)
        progress = result["execution_progress"]
        assert progress["total"] == 3
        assert progress["executed"] == 1
        assert progress["skipped"] == 1
        assert progress["failed"] == 1
        assert progress["percent_complete"] == pytest.approx(33.3, abs=0.1)

    async def test_status_zero_trades(self, mock_session: AsyncMock) -> None:
        svc = RebalanceService(mock_session)
        proposal = _make_proposal(status="draft")

        mock_session.execute.side_effect = [
            _exec(scalar_one=proposal),
            _exec(scalars_all=[]),
            _exec(scalar_one=proposal),
            _exec(scalars_all=[]),
        ]

        result = await svc.get_rebalance_status(proposal.id)
        assert result["execution_progress"]["total"] == 0
        assert result["execution_progress"]["percent_complete"] == 0


# ---------------------------------------------------------------------------
# Get drift summary
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestGetDriftSummary:
    async def test_drift_summary_no_snapshot(
        self, mock_session: AsyncMock, portfolio_id: uuid.UUID
    ) -> None:
        svc = RebalanceService(mock_session)
        model = _make_portfolio_model(id=portfolio_id, name="Test")

        mock_session.execute.side_effect = [
            _exec(scalar_one=model),      # _get_portfolio: ModelPortfolio
            _exec(scalars_all=[]),         # _get_portfolio: nav
            _exec(scalars_all=[]),         # _get_positions
            _exec(scalar_one=None),        # snapshot query
        ]

        result = await svc.get_drift_summary(portfolio_id)
        assert result["portfolio_name"] == "Test"
        assert result["snapshot_date"] is None
        assert result["max_drift"] == 0.0


# ---------------------------------------------------------------------------
# Trade calculation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestCalculateRebalance:
    async def test_no_trades_when_within_threshold(
        self, mock_session: AsyncMock, portfolio_id: uuid.UUID
    ) -> None:
        svc = RebalanceService(mock_session)
        model = _make_portfolio_model(id=portfolio_id)
        pos = _make_position(
            portfolio_id=portfolio_id, ticker_symbol="PETR4", weight_pct=0.20
        )

        mock_session.execute.side_effect = [
            _exec(scalar_one=model),              # _get_portfolio
            _exec(scalars_all=[(Decimal("100"), Decimal("10000"))]),  # nav
            _exec(scalars_all=[pos]),              # _get_positions
        ]

        trades = await svc.calculate_rebalance(portfolio_id, {"PETR4": 0.2005})
        # delta = 0.0005 < MIN_TRADE_SIZE_PCT → no trades
        assert trades == []

    async def test_generates_buy_trade(
        self, mock_session: AsyncMock, portfolio_id: uuid.UUID
    ) -> None:
        svc = RebalanceService(mock_session)
        model = _make_portfolio_model(id=portfolio_id)
        pos = _make_position(
            portfolio_id=portfolio_id, ticker_symbol="PETR4", weight_pct=0.10
        )

        mock_session.execute.side_effect = [
            _exec(scalar_one=model),
            _exec(scalars_all=[(Decimal("100"), Decimal("10000"))]),
            _exec(scalars_all=[pos]),
        ]

        trades = await svc.calculate_rebalance(portfolio_id, {"PETR4": 0.30})
        assert len(trades) == 1
        assert trades[0]["side"] == "buy"
        assert trades[0]["delta"] == pytest.approx(0.20, abs=0.001)

    async def test_generates_sell_trade(
        self, mock_session: AsyncMock, portfolio_id: uuid.UUID
    ) -> None:
        svc = RebalanceService(mock_session)
        model = _make_portfolio_model(id=portfolio_id)
        pos = _make_position(
            portfolio_id=portfolio_id, ticker_symbol="PETR4", weight_pct=0.30
        )

        mock_session.execute.side_effect = [
            _exec(scalar_one=model),
            _exec(scalars_all=[(Decimal("100"), Decimal("10000"))]),
            _exec(scalars_all=[pos]),
        ]

        trades = await svc.calculate_rebalance(portfolio_id, {"PETR4": 0.10})
        assert len(trades) == 1
        assert trades[0]["side"] == "sell"

    async def test_new_ticker_generates_buy(
        self, mock_session: AsyncMock, portfolio_id: uuid.UUID
    ) -> None:
        svc = RebalanceService(mock_session)
        model = _make_portfolio_model(id=portfolio_id)

        mock_session.execute.side_effect = [
            _exec(scalar_one=model),
            _exec(scalars_all=[]),
            _exec(scalars_all=[]),
        ]

        trades = await svc.calculate_rebalance(portfolio_id, {"VALE3": 0.15})
        assert len(trades) == 1
        assert trades[0]["ticker"] == "VALE3"
        assert trades[0]["side"] == "buy"

    async def test_trades_sorted_by_delta_descending(
        self, mock_session: AsyncMock, portfolio_id: uuid.UUID
    ) -> None:
        svc = RebalanceService(mock_session)
        model = _make_portfolio_model(id=portfolio_id)

        mock_session.execute.side_effect = [
            _exec(scalar_one=model),
            _exec(scalars_all=[]),
            _exec(scalars_all=[]),
        ]

        trades = await svc.calculate_rebalance(
            portfolio_id, {"A": 0.10, "B": 0.30, "C": 0.05}
        )
        deltas = [abs(t["delta"]) for t in trades]
        assert deltas == sorted(deltas, reverse=True)
