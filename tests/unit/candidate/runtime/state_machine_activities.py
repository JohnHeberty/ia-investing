from __future__ import annotations

from unittest.mock import patch

import pytest
from temporalio.exceptions import ApplicationError

from ia_investing.orchestration.activities.state_machine import _MACHINES, apply_state_transition


# ---------------------------------------------------------------------------
# Tests: _MACHINES registry
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestMachinesRegistry:
    def test_all_five_types_registered(self):
        assert set(_MACHINES.keys()) == {"thesis", "committee", "portfolio", "risk", "execution"}

    def test_each_entry_has_model_class_and_factory(self):
        for model_cls, factory in _MACHINES.values():
            assert hasattr(model_cls, "model_validate") or hasattr(model_cls, "model_config")
            assert callable(factory)


# ---------------------------------------------------------------------------
# Tests: apply_state_transition — valid transitions
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestApplyTransitionValid:
    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_thesis_submit(self, mock_emit):
        result = await apply_state_transition(
            "thesis",
            {"state": "draft"},
            "submit",
        )
        assert result["state"] == "under_review"
        assert mock_emit.call_count == 1
        args, kwargs = mock_emit.call_args
        assert args[0] == "state_transition"
        assert kwargs["outcome"] == "allow"

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_committee_convene(self, mock_emit):
        result = await apply_state_transition(
            "committee",
            {"state": "scheduled"},
            "convene",
        )
        assert result["state"] == "in_session"

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_execution_pending_to_validated(self, mock_emit):
        result = await apply_state_transition(
            "execution",
            {"state": "pending"},
            "run_validation",
        )
        assert result["state"] == "validated"

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_portfolio_allocating_to_rebalancing(self, mock_emit):
        result = await apply_state_transition(
            "portfolio",
            {"state": "allocating", "nav": 1000.0},
            "rebalance",
        )
        assert result["state"] == "rebalancing"

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_risk_normal_to_monitoring(self, mock_emit):
        result = await apply_state_transition(
            "risk",
            {"state": "normal"},
            "detect_anomaly",
        )
        assert result["state"] == "monitoring"


# ---------------------------------------------------------------------------
# Tests: apply_state_transition — conditional guards
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestApplyTransitionGuards:
    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_thesis_approve_blocked_without_evidence(self, mock_emit):
        with pytest.raises(ApplicationError, match="StateTransitionError") as exc_info:
            await apply_state_transition(
                "thesis",
                {"state": "under_review", "has_required_evidence": False},
                "approve",
            )
        assert exc_info.value.non_retryable is True

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_thesis_approve_allowed_with_evidence(self, mock_emit):
        result = await apply_state_transition(
            "thesis",
            {"state": "under_review", "has_required_evidence": True},
            "approve",
        )
        assert result["state"] == "approved"

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_committee_start_voting_blocked_no_quorum(self, mock_emit):
        with pytest.raises(ApplicationError):
            await apply_state_transition(
                "committee",
                {"state": "in_session", "total_members": 5, "present_members": 1},
                "start_voting",
            )

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_committee_start_voting_allowed_with_quorum(self, mock_emit):
        result = await apply_state_transition(
            "committee",
            {"state": "in_session", "total_members": 5, "present_members": 3},
            "start_voting",
        )
        assert result["state"] == "voting"

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_execution_dispatch_blocked_insufficient_balance(self, mock_emit):
        with pytest.raises(ApplicationError):
            await apply_state_transition(
                "execution",
                {"state": "queued", "available_balance": 100.0, "required_amount": 500.0},
                "dispatch",
            )

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_execution_dispatch_allowed_sufficient_balance(self, mock_emit):
        result = await apply_state_transition(
            "execution",
            {"state": "queued", "available_balance": 1000.0, "required_amount": 500.0},
            "dispatch",
        )
        assert result["state"] == "dispatched"

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_portfolio_rebalance_blocked_nav_zero(self, mock_emit):
        with pytest.raises(ApplicationError):
            await apply_state_transition(
                "portfolio",
                {"state": "allocating", "nav": 0.0},
                "rebalance",
            )

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_risk_breach_blocked_below_threshold(self, mock_emit):
        with pytest.raises(ApplicationError):
            await apply_state_transition(
                "risk",
                {"state": "monitoring", "threshold_value": 100.0, "current_value": 50.0},
                "breach",
            )

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_risk_breach_allowed_above_threshold(self, mock_emit):
        result = await apply_state_transition(
            "risk",
            {"state": "monitoring", "threshold_value": 100.0, "current_value": 150.0},
            "breach",
        )
        assert result["state"] == "breached"


# ---------------------------------------------------------------------------
# Tests: apply_state_transition — invalid
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestApplyTransitionInvalid:
    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_unknown_entity_type_raises(self, mock_emit):
        with pytest.raises(ApplicationError, match="Unknown state machine entity type"):
            await apply_state_transition("nonexistent", {"state": "s"}, "trigger")

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_invalid_trigger_raises(self, mock_emit):
        with pytest.raises(ApplicationError, match="StateTransitionError"):
            await apply_state_transition("thesis", {"state": "draft"}, "nonexistent_trigger")

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_invalid_transition_emits_failure_event(self, mock_emit):
        with pytest.raises(ApplicationError):
            await apply_state_transition("thesis", {"state": "draft"}, "nonexistent_trigger")
        assert mock_emit.call_count == 1
        args, kwargs = mock_emit.call_args
        assert args[0] == "state_transition_failure"
        assert kwargs["outcome"] == "deny"


# ---------------------------------------------------------------------------
# Tests: side effects on enter/exit
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestSideEffects:
    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_thesis_activate_sets_monitoring_scheduled(self, mock_emit):
        result = await apply_state_transition(
            "thesis",
            {"state": "approved"},
            "activate",
        )
        assert result["state"] == "active"
        assert result["monitoring_scheduled"] is True

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_execution_fail_sets_alert(self, mock_emit):
        result = await apply_state_transition(
            "execution",
            {"state": "pending"},
            "fail",
        )
        assert result["state"] == "failed"
        assert result["alert_triggered"] is True

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_portfolio_hold_sets_orders_frozen(self, mock_emit):
        result = await apply_state_transition(
            "portfolio",
            {"state": "monitoring", "nav": 100.0},
            "hold",
        )
        assert result["state"] == "compliance_hold"
        assert result["orders_frozen"] is True

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_risk_breach_sets_alerted(self, mock_emit):
        result = await apply_state_transition(
            "risk",
            {"state": "monitoring", "threshold_value": 0.0, "current_value": 1.0},
            "breach",
        )
        assert result["state"] == "breached"
        assert result["risk_team_alerted"] is True

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_risk_investigate_sets_auto_escalated(self, mock_emit):
        result = await apply_state_transition(
            "risk",
            {"state": "breached", "threshold_value": 0.0, "current_value": 1.0},
            "investigate",
        )
        assert result["state"] == "escalated"
        assert result["auto_escalated"] is True

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.state_machine.emit_security_event")
    async def test_committee_publish_sets_members_notified(self, mock_emit):
        result = await apply_state_transition(
            "committee",
            {"state": "decided"},
            "publish",
        )
        assert result["state"] == "published"
        assert result["members_notified"] is True
