"""Tests for RebalanceService — org scoping, drift calculation, proposal lifecycle."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from ia_investing.application.rebalance_service import (
    MAX_CONCENTRATION_PCT,
    RebalanceService,
)


@pytest.fixture()
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture()
def org_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def portfolio_id() -> uuid.UUID:
    return uuid.uuid4()


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


class TestDriftCalculation:
    def test_empty_allocations(self):
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._compute_drift({}, {})
        assert result["max_drift"] == 0.0
        assert result["total_drift"] == 0.0
        assert result["items"] == []

    def test_green_severity(self):
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._compute_drift({"PETR4": 0.10}, {"PETR4": 0.105})
        assert result["items"][0]["severity"] == "green"

    def test_yellow_severity(self):
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._compute_drift({"PETR4": 0.10}, {"PETR4": 0.12})
        assert result["items"][0]["severity"] == "yellow"

    def test_red_severity(self):
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._compute_drift({"PETR4": 0.10}, {"PETR4": 0.15})
        assert result["items"][0]["severity"] == "red"

    def test_sorted_by_magnitude(self):
        svc = RebalanceService.__new__(RebalanceService)
        current = {"A": 0.10, "B": 0.20, "C": 0.30}
        target = {"A": 0.15, "B": 0.20, "C": 0.25}
        result = svc._compute_drift(current, target)
        drifts = [item["drift"] for item in result["items"]]
        assert drifts == sorted(drifts, reverse=True)

    def test_max_and_total(self):
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._compute_drift({"A": 0.10, "B": 0.20}, {"A": 0.15, "B": 0.25})
        assert result["max_drift"] == 0.05
        assert result["total_drift"] == pytest.approx(0.10)


class TestComplianceCheck:
    def test_passes(self):
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._check_compliance({"PETR4": 0.15, "VALE3": 0.10})
        assert result["passed"] is True
        assert result["issues"] == []

    def test_fails_concentration(self):
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._check_compliance({"PETR4": 0.30})
        assert result["passed"] is False
        assert len(result["issues"]) == 1
        assert "PETR4" in result["issues"][0]

    def test_exact_limit_passes(self):
        svc = RebalanceService.__new__(RebalanceService)
        result = svc._check_compliance({"PETR4": float(MAX_CONCENTRATION_PCT)})
        assert result["passed"] is True


class TestProposalLifecycle:
    async def test_approve_rejects_non_draft(self, mock_session):
        svc = RebalanceService(mock_session)
        proposal = MagicMock()
        proposal.status = "approved"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = proposal
        mock_session.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Cannot approve"):
            await svc.approve_rebalance(uuid.uuid4(), "user-1")

    async def test_cancel_rejects_completed(self, mock_session):
        svc = RebalanceService(mock_session)
        proposal = MagicMock()
        proposal.status = "completed"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = proposal
        mock_session.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Cannot cancel"):
            await svc.cancel_rebalance(uuid.uuid4(), "reason")

    async def test_execute_rejects_draft(self, mock_session):
        svc = RebalanceService(mock_session)
        proposal = MagicMock()
        proposal.status = "draft"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = proposal
        mock_session.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Cannot execute"):
            await svc.execute_rebalance_step(uuid.uuid4(), [uuid.uuid4()])

    async def test_complete_rejects_draft(self, mock_session):
        svc = RebalanceService(mock_session)
        proposal = MagicMock()
        proposal.status = "draft"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = proposal
        mock_session.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Cannot complete"):
            await svc.complete_rebalance(uuid.uuid4())


class TestGetRebalanceStatus:
    async def test_zero_trades_no_division_by_zero(self, mock_session):
        svc = RebalanceService(mock_session)
        proposal = MagicMock()
        proposal.status = "draft"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = proposal
        mock_session.execute.return_value = mock_result

        trades_result = MagicMock()
        trades_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = trades_result

        status = await svc.get_rebalance_status(uuid.uuid4())
        assert status["execution_progress"]["total"] == 0
        assert status["execution_progress"]["percent_complete"] == 0
