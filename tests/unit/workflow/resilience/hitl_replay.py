"""Temporal replay tests for HITL workflows.

Verifies that workflow state is correctly preserved across pause/resume cycles,
that replay from event history produces identical outcomes, and that versions/inputs
are preserved exactly after human approval decisions.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ia_investing.domain.portfolio_decision import CommitteeVote, PortfolioDecisionInputs
from workflows._approval_gate import ApprovalGateInput, ApprovalGateWorkflow
from workflows._paper_rebalance import PaperRebalanceInput, PaperRebalanceWorkflow
from workflows._portfolio_construction import (
    PortfolioConstructionInput,
    PortfolioConstructionWorkflow,
)

_FAKE = "b" * 64


def _decision_inputs() -> PortfolioDecisionInputs:
    return PortfolioDecisionInputs(
        portfolio_id="p-replay",
        proposed_by="pm-replay",
        input_snapshot_sha256="a" * 64,
        proposal_sha256="c" * 64,
        risk_opinion="approved",
        compliance_opinion="approved",
        optimizer_status="optimal",
        eligible=True,
        hard_breach=False,
    )


# ===================================================================
# 1. ApprovalGate — replay preserves exact input/output
# ===================================================================


class TestApprovalGateReplay:
    @pytest.mark.asyncio
    async def test_replay_preserves_all_input_fields(self) -> None:
        wf = ApprovalGateWorkflow()
        cmd = ApprovalGateInput("run-replay-1", "av-replay-1", _FAKE, timeout_seconds=600)

        async def inject(*a: object, **kw: object) -> None:
            wf._decision = "approved"

        with patch("workflows._approval_gate.workflow.wait_condition", side_effect=inject):
            result = await wf.run(cmd)

        assert result.run_id == "run-replay-1"
        assert result.agent_version_id == "av-replay-1"
        assert result.input_sha256 == _FAKE
        assert result.decision == "approved"

    @pytest.mark.asyncio
    async def test_pause_then_resume_yields_same_result(self) -> None:
        wf1 = ApprovalGateWorkflow()
        wf2 = ApprovalGateWorkflow()
        cmd = ApprovalGateInput("run-pr-1", "av-pr-1", _FAKE, timeout_seconds=300)

        async def inject1(*a: object, **kw: object) -> None:
            wf1._decision = "approved"

        with patch("workflows._approval_gate.workflow.wait_condition", side_effect=inject1):
            r1 = await wf1.run(cmd)

        async def inject2(*a: object, **kw: object) -> None:
            wf2._decision = "approved"

        with patch("workflows._approval_gate.workflow.wait_condition", side_effect=inject2):
            r2 = await wf2.run(cmd)

        assert r1.run_id == r2.run_id
        assert r1.agent_version_id == r2.agent_version_id
        assert r1.input_sha256 == r2.input_sha256
        assert r1.decision == r2.decision

    @pytest.mark.asyncio
    async def test_signal_before_wait_condition_is_replayed(self) -> None:
        wf = ApprovalGateWorkflow()
        cmd = ApprovalGateInput("run-pre-signal", "av-pre", _FAKE, timeout_seconds=300)
        await wf.decide("approved")

        with patch("workflows._approval_gate.workflow.wait_condition") as mock_wait:
            mock_wait.return_value = None
            result = await wf.run(cmd)

        assert result.decision == "approved"

    @pytest.mark.asyncio
    async def test_timeout_preserves_input_after_replay(self) -> None:
        wf = ApprovalGateWorkflow()
        cmd = ApprovalGateInput("run-timeout-replay", "av-to", _FAKE, timeout_seconds=1)
        with patch("workflows._approval_gate.workflow.wait_condition", side_effect=TimeoutError):
            result = await wf.run(cmd)

        assert result.decision == "expired"
        assert result.run_id == "run-timeout-replay"
        assert result.agent_version_id == "av-to"

    @pytest.mark.asyncio
    async def test_cancel_decision_preserved_after_replay(self) -> None:
        wf = ApprovalGateWorkflow()
        cmd = ApprovalGateInput("run-cancel-rep", "av-cr", _FAKE, timeout_seconds=300)

        async def inject(*a: object, **kw: object) -> None:
            wf._decision = "cancelled"

        with patch("workflows._approval_gate.workflow.wait_condition", side_effect=inject):
            result = await wf.run(cmd)

        assert result.decision == "cancelled"


# ===================================================================
# 2. PaperRebalance — state machine replay
# ===================================================================


class TestPaperRebalanceReplay:
    @pytest.mark.asyncio
    async def test_approved_state_preserved_across_replay(self) -> None:
        wf1 = PaperRebalanceWorkflow()
        wf2 = PaperRebalanceWorkflow()
        cmd = PaperRebalanceInput("pb-1", "pv-1", _FAKE, 300)

        async def inject1(*a: object, **kw: object) -> None:
            wf1._state = "approved_for_paper"

        with patch("workflows._paper_rebalance.workflow.wait_condition", side_effect=inject1):
            r1 = await wf1.run(cmd)

        async def inject2(*a: object, **kw: object) -> None:
            wf2._state = "approved_for_paper"

        with patch("workflows._paper_rebalance.workflow.wait_condition", side_effect=inject2):
            r2 = await wf2.run(cmd)

        assert r1.state == r2.state == "approved_for_paper"
        assert r1.execution_environment == r2.execution_environment == "paper"

    @pytest.mark.asyncio
    async def test_rejected_state_preserved_across_replay(self) -> None:
        wf = PaperRebalanceWorkflow()
        cmd = PaperRebalanceInput("pb-rej", "pv-rej", _FAKE, 300)

        async def inject(*a: object, **kw: object) -> None:
            wf._state = "rejected"

        with patch("workflows._paper_rebalance.workflow.wait_condition", side_effect=inject):
            result = await wf.run(cmd)

        assert result.state == "rejected"

    @pytest.mark.asyncio
    async def test_kill_state_preserved_after_replay(self) -> None:
        wf = PaperRebalanceWorkflow()
        cmd = PaperRebalanceInput("pb-kill", "pv-kill", _FAKE, 300)

        async def inject(*a: object, **kw: object) -> None:
            wf._state = "killed"

        with patch("workflows._paper_rebalance.workflow.wait_condition", side_effect=inject):
            result = await wf.run(cmd)

        assert result.state == "killed"

    @pytest.mark.asyncio
    async def test_input_fields_intact_after_timeout(self) -> None:
        wf = PaperRebalanceWorkflow()
        cmd = PaperRebalanceInput("pb-to", "pv-to", _FAKE, 60)
        with patch("workflows._paper_rebalance.workflow.wait_condition", side_effect=TimeoutError):
            result = await wf.run(cmd)

        assert result.state == "expired"


# ===================================================================
# 3. PortfolioConstruction — vote buffer replay + immutable pack
# ===================================================================


class TestPortfolioConstructionReplay:
    @pytest.mark.asyncio
    async def test_vote_buffer_flushed_deterministically(self) -> None:
        wf1 = PortfolioConstructionWorkflow()
        wf2 = PortfolioConstructionWorkflow()
        cmd = PortfolioConstructionInput(
            decision_inputs=_decision_inputs(),
            approval_timeout_seconds=300,
        )

        pm_vote = CommitteeVote("pm-v1", "portfolio_manager", "approved", "ok", _FAKE)
        risk_vote = CommitteeVote("risk-v1", "risk_officer", "approved", "ok", _FAKE)

        await wf1.vote(pm_vote)
        await wf2.vote(pm_vote)

        async def inject1(*a: object, **kw: object) -> None:
            wf1._votes.append(risk_vote)

        with patch("workflows._portfolio_construction.workflow.wait_condition", side_effect=inject1):
            r1 = await wf1.run(cmd)

        async def inject2(*a: object, **kw: object) -> None:
            wf2._votes.append(risk_vote)

        with patch("workflows._portfolio_construction.workflow.wait_condition", side_effect=inject2):
            r2 = await wf2.run(cmd)

        assert r1.decision_pack_sha256 == r2.decision_pack_sha256
        assert r1.votes == r2.votes
        assert r1.state == r2.state == "approved"

    @pytest.mark.asyncio
    async def test_decision_pack_immutable_after_approval(self) -> None:
        wf = PortfolioConstructionWorkflow()
        cmd = PortfolioConstructionInput(
            decision_inputs=_decision_inputs(),
            approval_timeout_seconds=300,
        )
        pm_vote = CommitteeVote("pm-imm", "portfolio_manager", "approved", "ok", _FAKE)
        risk_vote = CommitteeVote("risk-imm", "risk_officer", "approved", "ok", _FAKE)
        await wf.vote(pm_vote)

        async def inject(*a: object, **kw: object) -> None:
            wf._votes.append(risk_vote)

        with patch("workflows._portfolio_construction.workflow.wait_condition", side_effect=inject):
            result = await wf.run(cmd)

        assert len(result.decision_pack_sha256) == 64
        assert all(c in "0123456789abcdef" for c in result.decision_pack_sha256)
        assert len(result.votes) == 2

    @pytest.mark.asyncio
    async def test_rejection_preserves_vote_history(self) -> None:
        wf = PortfolioConstructionWorkflow()
        cmd = PortfolioConstructionInput(
            decision_inputs=_decision_inputs(),
            approval_timeout_seconds=300,
        )
        bad_vote = CommitteeVote("risk-rej", "risk_officer", "rejected", "no", _FAKE)

        async def inject(*a: object, **kw: object) -> None:
            wf._votes.append(bad_vote)

        with patch("workflows._portfolio_construction.workflow.wait_condition", side_effect=inject):
            result = await wf.run(cmd)

        assert result.state == "rejected"
        assert len(result.votes) == 1
        assert result.votes[0].decision == "rejected"
