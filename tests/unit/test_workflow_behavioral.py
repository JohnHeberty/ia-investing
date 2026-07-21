"""Behavioral tests for all 5 Temporal workflows.

Covers: approval, rejection, timeout, cancel, idempotency, signal buffering,
conditional approval, and full run-to-completion with mocked Temporal primitives.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from ia_investing.domain.portfolio_decision import CommitteeVote
from workflows._approval_gate import ApprovalGateInput, ApprovalGateResult, ApprovalGateWorkflow
from workflows._paper_rebalance import PaperRebalanceInput, PaperRebalanceResult, PaperRebalanceWorkflow
from workflows._policy_event import PolicyEventInput, PolicyEventResult, PolicyEventWorkflow
from workflows._portfolio_construction import (
    PortfolioConstructionInput,
    PortfolioConstructionWorkflow,
)
from workflows._thesis_review import ThesisReviewInput, ThesisReviewResult, ThesisReviewWorkflow

_FAKE = "a" * 64


def _pm_vote(*, decision: str = "approved") -> CommitteeVote:
    return CommitteeVote("pm-bob", "portfolio_manager", decision, "ok", _FAKE)


def _risk_vote(*, decision: str = "approved") -> CommitteeVote:
    return CommitteeVote("risk-carol", "risk_officer", decision, "ok", _FAKE)


async def _async_run(coro):
    return await coro


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ===================================================================
# 1. ApprovalGateWorkflow
# ===================================================================


class TestApprovalGateBehavioral:
    @pytest.mark.asyncio
    async def test_approval_full_run(self) -> None:
        wf = ApprovalGateWorkflow()
        cmd = ApprovalGateInput("r-1", "av-1", _FAKE, timeout_seconds=300)

        async def inject(*a: object, **kw: object) -> None:
            wf._decision = "approved"

        with patch("workflows._approval_gate.workflow.wait_condition", side_effect=inject):
            r = await wf.run(cmd)
        assert isinstance(r, ApprovalGateResult)
        assert r.decision == "approved"
        assert r.run_id == "r-1"

    @pytest.mark.asyncio
    async def test_rejection_full_run(self) -> None:
        wf = ApprovalGateWorkflow()
        cmd = ApprovalGateInput("r-2", "av-2", _FAKE, timeout_seconds=300)

        async def inject(*a: object, **kw: object) -> None:
            wf._decision = "rejected"

        with patch("workflows._approval_gate.workflow.wait_condition", side_effect=inject):
            r = await wf.run(cmd)
        assert r.decision == "rejected"

    @pytest.mark.asyncio
    async def test_cancel_full_run(self) -> None:
        wf = ApprovalGateWorkflow()
        cmd = ApprovalGateInput("r-3", "av-3", _FAKE, timeout_seconds=300)

        async def inject(*a: object, **kw: object) -> None:
            wf._decision = "cancelled"

        with patch("workflows._approval_gate.workflow.wait_condition", side_effect=inject):
            r = await wf.run(cmd)
        assert r.decision == "cancelled"

    @pytest.mark.asyncio
    async def test_timeout_full_run(self) -> None:
        wf = ApprovalGateWorkflow()
        cmd = ApprovalGateInput("r-4", "av-4", _FAKE, timeout_seconds=60)
        with patch("workflows._approval_gate.workflow.wait_condition", side_effect=TimeoutError):
            r = await wf.run(cmd)
        assert r.decision == "expired"

    @pytest.mark.asyncio
    async def test_idempotent_signal(self) -> None:
        wf = ApprovalGateWorkflow()
        cmd = ApprovalGateInput("r-5", "av-5", _FAKE, timeout_seconds=300)

        async def inject(*a: object, **kw: object) -> None:
            wf._decision = "approved"

        with patch("workflows._approval_gate.workflow.wait_condition", side_effect=inject):
            await wf.run(cmd)
        await wf.decide("rejected")
        assert wf.state() == "approved"

    @pytest.mark.asyncio
    async def test_preserves_input_fields(self) -> None:
        wf = ApprovalGateWorkflow()
        cmd = ApprovalGateInput("run-42", "av-99", _FAKE, timeout_seconds=600)
        with patch("workflows._approval_gate.workflow.wait_condition", side_effect=TimeoutError):
            r = await wf.run(cmd)
        assert r.run_id == "run-42" and r.agent_version_id == "av-99"

    def test_query_initial(self) -> None:
        assert ApprovalGateWorkflow().state() == "awaiting_approval"

    def test_invalid_signal(self) -> None:
        wf = ApprovalGateWorkflow()
        with pytest.raises(ValueError, match="invalid"):
            _run(wf.decide("bogus"))

    def test_zero_timeout(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            _run(ApprovalGateWorkflow().run(ApprovalGateInput("r", "a", _FAKE, 0)))


# ===================================================================
# 2. PaperRebalanceWorkflow
# ===================================================================


class TestPaperRebalanceBehavioral:
    @pytest.mark.asyncio
    async def test_approval_full_run(self) -> None:
        wf = PaperRebalanceWorkflow()
        cmd = PaperRebalanceInput("p-1", "pv-1", _FAKE, 300)

        async def inject(*a: object, **kw: object) -> None:
            wf._state = "approved_for_paper"

        with patch("workflows._paper_rebalance.workflow.wait_condition", side_effect=inject):
            r = await wf.run(cmd)
        assert isinstance(r, PaperRebalanceResult)
        assert r.state == "approved_for_paper"
        assert r.execution_environment == "paper"

    @pytest.mark.asyncio
    async def test_rejection_full_run(self) -> None:
        wf = PaperRebalanceWorkflow()
        cmd = PaperRebalanceInput("p-2", "pv-2", _FAKE, 300)

        async def inject(*a: object, **kw: object) -> None:
            wf._state = "rejected"

        with patch("workflows._paper_rebalance.workflow.wait_condition", side_effect=inject):
            r = await wf.run(cmd)
        assert r.state == "rejected"

    @pytest.mark.asyncio
    async def test_cancel_full_run(self) -> None:
        wf = PaperRebalanceWorkflow()
        cmd = PaperRebalanceInput("p-3", "pv-3", _FAKE, 300)

        async def inject(*a: object, **kw: object) -> None:
            wf._state = "cancelled"

        with patch("workflows._paper_rebalance.workflow.wait_condition", side_effect=inject):
            r = await wf.run(cmd)
        assert r.state == "cancelled"

    @pytest.mark.asyncio
    async def test_timeout_full_run(self) -> None:
        wf = PaperRebalanceWorkflow()
        cmd = PaperRebalanceInput("p-4", "pv-4", _FAKE, 60)
        with patch("workflows._paper_rebalance.workflow.wait_condition", side_effect=TimeoutError):
            r = await wf.run(cmd)
        assert r.state == "expired"

    @pytest.mark.asyncio
    async def test_kill_full_run(self) -> None:
        wf = PaperRebalanceWorkflow()
        cmd = PaperRebalanceInput("p-5", "pv-5", _FAKE, 300)

        async def inject(*a: object, **kw: object) -> None:
            wf._state = "killed"

        with patch("workflows._paper_rebalance.workflow.wait_condition", side_effect=inject):
            r = await wf.run(cmd)
        assert r.state == "killed"

    def test_kill_from_awaiting(self) -> None:
        wf = PaperRebalanceWorkflow()
        _run(wf.kill())
        assert wf.state() == "killed"

    def test_kill_from_approved(self) -> None:
        wf = PaperRebalanceWorkflow()
        _run(wf.decide("approved_for_paper"))
        _run(wf.kill())
        assert wf.state() == "killed"

    def test_kill_ignored_after_rejected(self) -> None:
        wf = PaperRebalanceWorkflow()
        _run(wf.decide("rejected"))
        _run(wf.kill())
        assert wf.state() == "rejected"

    def test_kill_ignored_after_cancelled(self) -> None:
        wf = PaperRebalanceWorkflow()
        _run(wf.decide("cancelled"))
        _run(wf.kill())
        assert wf.state() == "cancelled"

    def test_idempotent_decide(self) -> None:
        wf = PaperRebalanceWorkflow()
        _run(wf.decide("approved_for_paper"))
        _run(wf.decide("rejected"))
        assert wf.state() == "approved_for_paper"

    def test_invalid_signal(self) -> None:
        with pytest.raises(ValueError, match="invalid"):
            _run(PaperRebalanceWorkflow().decide("bogus"))

    def test_query_initial(self) -> None:
        assert PaperRebalanceWorkflow().state() == "awaiting_approval"

    def test_zero_timeout(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            _run(PaperRebalanceWorkflow().run(PaperRebalanceInput("p", "pv", _FAKE, 0)))


# ===================================================================
# 3. PolicyEventWorkflow
# ===================================================================


class TestPolicyEventBehavioral:
    @pytest.mark.asyncio
    async def test_material_approval_full_run(self) -> None:
        wf = PolicyEventWorkflow()
        cmd = PolicyEventInput("po-1", 1, _FAKE, material=True, review_timeout_seconds=300)

        async def inject(*a: object, **kw: object) -> None:
            wf._decision = "approved"

        with patch("workflows._policy_event.workflow.wait_condition", side_effect=inject):
            r = await wf.run(cmd)
        assert isinstance(r, PolicyEventResult)
        assert r.decision == "approved"

    @pytest.mark.asyncio
    async def test_material_rejection_full_run(self) -> None:
        wf = PolicyEventWorkflow()
        cmd = PolicyEventInput("po-2", 1, _FAKE, material=True, review_timeout_seconds=300)

        async def inject(*a: object, **kw: object) -> None:
            wf._decision = "rejected"

        with patch("workflows._policy_event.workflow.wait_condition", side_effect=inject):
            r = await wf.run(cmd)
        assert r.decision == "rejected"

    @pytest.mark.asyncio
    async def test_material_timeout(self) -> None:
        wf = PolicyEventWorkflow()
        cmd = PolicyEventInput("po-3", 1, _FAKE, material=True, review_timeout_seconds=60)
        with patch("workflows._policy_event.workflow.wait_condition", side_effect=TimeoutError):
            r = await wf.run(cmd)
        assert r.decision == "expired"

    @pytest.mark.asyncio
    async def test_non_material_skips_review(self) -> None:
        wf = PolicyEventWorkflow()
        cmd = PolicyEventInput("po-4", 1, _FAKE, material=False, review_timeout_seconds=300)
        r = await wf.run(cmd)
        assert r.decision == "not_required"

    def test_idempotent_signal(self) -> None:
        wf = PolicyEventWorkflow()
        _run(wf.review("approved"))
        _run(wf.review("rejected"))
        assert wf.state() == "approved"

    def test_invalid_signal(self) -> None:
        with pytest.raises(ValueError, match="invalid"):
            _run(PolicyEventWorkflow().review("bogus"))

    def test_query_initial(self) -> None:
        assert PolicyEventWorkflow().state() == "awaiting_review"

    def test_zero_timeout(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            _run(PolicyEventWorkflow().run(PolicyEventInput("po", 1, _FAKE, True, 0)))

    def test_zero_version(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            _run(PolicyEventWorkflow().run(PolicyEventInput("po", 0, _FAKE, True, 300)))


# ===================================================================
# 4. PortfolioConstructionWorkflow (behavioral gap tests)
# ===================================================================


class TestPortfolioConstructionBehavioral:
    def _precomputed_cmd(self) -> PortfolioConstructionInput:
        from ia_investing.domain.portfolio_decision import PortfolioDecisionInputs

        inputs = PortfolioDecisionInputs(
            portfolio_id="p-1",
            proposed_by="pm-alice",
            input_snapshot_sha256=_FAKE,
            proposal_sha256=_FAKE,
            risk_opinion="approved",
            compliance_opinion="approved",
            optimizer_status="optimal",
            eligible=True,
            hard_breach=False,
        )
        return PortfolioConstructionInput(decision_inputs=inputs, approval_timeout_seconds=300)

    @pytest.mark.asyncio
    async def test_self_approve_rejected_via_buffer(self) -> None:
        wf = PortfolioConstructionWorkflow()
        cmd = self._precomputed_cmd()
        self_vote = CommitteeVote("pm-alice", "portfolio_manager", "approved", "self", _FAKE)
        await wf.vote(self_vote)
        with pytest.raises(PermissionError, match="proposal author cannot approve"):
            await wf.run(cmd)

    @pytest.mark.asyncio
    async def test_duplicate_actor_rejected_via_buffer(self) -> None:
        wf = PortfolioConstructionWorkflow()
        cmd = self._precomputed_cmd()
        await wf.vote(_pm_vote())
        await wf.vote(_pm_vote())
        with pytest.raises(ValueError, match="already voted"):
            await wf.run(cmd)

    @pytest.mark.asyncio
    async def test_vote_buffer_flushed_to_review(self) -> None:
        wf = PortfolioConstructionWorkflow()
        cmd = self._precomputed_cmd()
        await wf.vote(_pm_vote())
        assert len(wf._pending_votes) == 1

        async def inject(*a: object, **kw: object) -> None:
            wf._votes.append(_risk_vote())

        with patch("workflows._portfolio_construction.workflow.wait_condition", side_effect=inject):
            result = await wf.run(cmd)
        assert wf._pending_votes == []
        assert len(wf._votes) == 2
        assert result.state == "approved"

    @pytest.mark.asyncio
    async def test_cancel_after_timeout_ignored(self) -> None:
        wf = PortfolioConstructionWorkflow()
        cmd = self._precomputed_cmd()
        with patch("workflows._portfolio_construction.workflow.wait_condition", side_effect=TimeoutError):
            result = await wf.run(cmd)
        assert result.state == "expired"
        await wf.cancel()
        assert wf.state() == "expired"

    @pytest.mark.asyncio
    async def test_rejection_via_vote_terminates(self) -> None:
        wf = PortfolioConstructionWorkflow()
        cmd = self._precomputed_cmd()

        async def inject(*a: object, **kw: object) -> None:
            wf._votes.append(_risk_vote(decision="rejected"))

        with patch("workflows._portfolio_construction.workflow.wait_condition", side_effect=inject):
            result = await wf.run(cmd)
        assert result.state == "rejected"

    @pytest.mark.asyncio
    async def test_conditional_approval_result(self) -> None:
        wf = PortfolioConstructionWorkflow()
        cmd = self._precomputed_cmd()

        async def inject(*a: object, **kw: object) -> None:
            wf._votes.append(
                CommitteeVote(
                    "pm-bob",
                    "portfolio_manager",
                    "approved_with_conditions",
                    "ok",
                    _FAKE,
                    conditions=("monitor leverage",),
                )
            )
            wf._votes.append(_risk_vote())

        with patch("workflows._portfolio_construction.workflow.wait_condition", side_effect=inject):
            result = await wf.run(cmd)
        assert result.state == "conditionally_approved"

    @pytest.mark.asyncio
    async def test_unauthorized_role_rejected_via_buffer(self) -> None:
        wf = PortfolioConstructionWorkflow()
        cmd = self._precomputed_cmd()
        bad_vote = CommitteeVote("intern-dave", "intern", "approved", "sure", _FAKE)
        await wf.vote(bad_vote)
        with pytest.raises(ValueError, match="not authorized"):
            await wf.run(cmd)


# ===================================================================
# 5. ThesisReviewWorkflow
# ===================================================================


class TestThesisReviewBehavioral:
    def _make_cmd(self, **overrides: object) -> ThesisReviewInput:
        return ThesisReviewInput(
            thesis_id=str(overrides.get("tid", "t-1")),
            thesis_version_id=str(overrides.get("tvid", "tv-1")),
            issuer_id=str(overrides.get("iid", "i-1")),
            data_as_of=str(overrides.get("dao", "2026-07-01T00:00:00+00:00")),
            knowledge_cutoff=str(overrides.get("kc", "2026-06-01T00:00:00+00:00")),
            specialist_capabilities=overrides.get("caps", ("filing", "news")),
            approval_timeout_seconds=int(overrides.get("timeout", 300)),
        )

    def _mock_activity(self) -> AsyncMock:
        async def route(name: str, **kwargs: object) -> dict[str, object]:
            if name == "load_thesis_context":
                return {"content_sha256": "c" * 64, "summary": "test"}
            if name.startswith("run_specialist_"):
                cap = name.replace("run_specialist_", "")
                return {
                    "verdict": "positive",
                    "confidence": 0.7,
                    "thesis_effect": "strengthen" if cap in ("filing", "news") else "no_change",
                    "key_claims": [],
                    "risks": [],
                    "contradictions": [],
                }
            return {}

        return AsyncMock(side_effect=route)

    @pytest.mark.asyncio
    async def test_approval_full_run(self) -> None:
        wf = ThesisReviewWorkflow()
        cmd = self._make_cmd()

        async def inject(*a: object, **kw: object) -> None:
            wf._decision = "approved"
            wf._reviewer = "reviewer-1"

        mock_act = self._mock_activity()
        with patch("workflows._thesis_review.workflow.execute_activity", side_effect=mock_act):
            with patch("workflows._thesis_review.workflow.wait_condition", side_effect=inject):
                r = await wf.run(cmd)
        assert isinstance(r, ThesisReviewResult)
        assert r.decision == "approved"
        assert r.approved_by == "reviewer-1"
        assert len(r.specialist_results) == 2

    @pytest.mark.asyncio
    async def test_rejection_full_run(self) -> None:
        wf = ThesisReviewWorkflow()
        cmd = self._make_cmd()

        async def inject(*a: object, **kw: object) -> None:
            wf._decision = "rejected"
            wf._reviewer = "reviewer-2"

        mock_act = self._mock_activity()
        with patch("workflows._thesis_review.workflow.execute_activity", side_effect=mock_act):
            with patch("workflows._thesis_review.workflow.wait_condition", side_effect=inject):
                r = await wf.run(cmd)
        assert r.decision == "rejected"

    @pytest.mark.asyncio
    async def test_cancel_full_run(self) -> None:
        wf = ThesisReviewWorkflow()
        cmd = self._make_cmd()

        async def inject(*a: object, **kw: object) -> None:
            wf._decision = "cancelled"

        mock_act = self._mock_activity()
        with patch("workflows._thesis_review.workflow.execute_activity", side_effect=mock_act):
            with patch("workflows._thesis_review.workflow.wait_condition", side_effect=inject):
                r = await wf.run(cmd)
        assert r.decision == "cancelled"

    @pytest.mark.asyncio
    async def test_timeout_full_run(self) -> None:
        wf = ThesisReviewWorkflow()
        cmd = self._make_cmd()
        mock_act = self._mock_activity()
        with patch("workflows._thesis_review.workflow.execute_activity", side_effect=mock_act):
            with patch("workflows._thesis_review.workflow.wait_condition", side_effect=TimeoutError):
                r = await wf.run(cmd)
        assert r.decision == "expired"
        assert r.status == "expired"

    @pytest.mark.asyncio
    async def test_contradiction_detected(self) -> None:
        wf = ThesisReviewWorkflow()
        cmd = self._make_cmd()

        async def route(name: str, **kwargs: object) -> dict[str, object]:
            if name == "load_thesis_context":
                return {"content_sha256": "c" * 64}
            if name == "run_specialist_filing":
                return {
                    "verdict": "positive",
                    "confidence": 0.8,
                    "thesis_effect": "strengthen",
                    "key_claims": [],
                    "risks": [],
                    "contradictions": [],
                }
            if name == "run_specialist_news":
                return {
                    "verdict": "negative",
                    "confidence": 0.6,
                    "thesis_effect": "weaken",
                    "key_claims": [],
                    "risks": [],
                    "contradictions": [],
                }
            return {}

        async def inject(*a: object, **kw: object) -> None:
            wf._decision = "approved"
            wf._reviewer = "r-1"

        with patch("workflows._thesis_review.workflow.execute_activity", side_effect=AsyncMock(side_effect=route)):
            with patch("workflows._thesis_review.workflow.wait_condition", side_effect=inject):
                r = await wf.run(cmd)
        assert "specialists_disagree_on_direction" in r.contradictions_found

    @pytest.mark.asyncio
    async def test_idempotent_approve(self) -> None:
        wf = ThesisReviewWorkflow()
        await wf.approve("r-1")
        await wf.reject("r-2")
        assert wf.state() == "approved"

    @pytest.mark.asyncio
    async def test_idempotent_reject(self) -> None:
        wf = ThesisReviewWorkflow()
        await wf.reject("r-1")
        await wf.approve("r-2")
        assert wf.state() == "rejected"

    @pytest.mark.asyncio
    async def test_specialist_results_query(self) -> None:
        wf = ThesisReviewWorkflow()
        assert wf.specialist_results() == []

    def test_query_initial(self) -> None:
        assert ThesisReviewWorkflow().state() == "running"

    def test_zero_timeout(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            _run(ThesisReviewWorkflow().run(self._make_cmd(timeout=0)))
