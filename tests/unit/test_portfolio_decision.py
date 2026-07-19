from __future__ import annotations

from dataclasses import replace

import pytest

from ia_investing.domain.portfolio_decision import (
    CommitteeVote,
    PortfolioDecisionInputs,
    decision_pack_sha256,
    validate_committee_vote,
    validate_decision_inputs,
)
from workflows import PortfolioConstructionWorkflow


def valid_inputs() -> PortfolioDecisionInputs:
    return PortfolioDecisionInputs(
        portfolio_id="portfolio-1",
        proposed_by="analyst",
        input_snapshot_sha256="a" * 64,
        proposal_sha256="b" * 64,
        risk_opinion="approved",
        compliance_opinion="approved",
        optimizer_status="optimal",
        eligible=True,
        hard_breach=False,
    )


def test_portfolio_decision_inputs_fail_closed() -> None:
    validate_decision_inputs(valid_inputs())
    blocked = replace(valid_inputs(), hard_breach=True)
    with pytest.raises(ValueError, match="hard risk breach"):
        validate_decision_inputs(blocked)


def test_committee_votes_enforce_four_eyes_roles_conditions_and_signatures() -> None:
    vote = CommitteeVote("manager", "portfolio_manager", "approved", "approved", "c" * 64)
    validate_committee_vote(vote, proposed_by="analyst", existing_actors=frozenset())
    with pytest.raises(PermissionError, match="author"):
        validate_committee_vote(
            CommitteeVote("analyst", "risk_officer", "approved", "ok", "d" * 64),
            proposed_by="analyst",
            existing_actors=frozenset(),
        )
    with pytest.raises(ValueError, match="conditions"):
        validate_committee_vote(
            CommitteeVote("risk", "risk_officer", "approved_with_conditions", "ok", "d" * 64),
            proposed_by="analyst",
            existing_actors=frozenset(),
        )


def test_decision_pack_hash_is_reproducible_and_vote_sensitive() -> None:
    vote = CommitteeVote("manager", "portfolio_manager", "approved", "approved", "c" * 64)
    assert decision_pack_sha256(valid_inputs(), (vote,)) == decision_pack_sha256(valid_inputs(), (vote,))
    rejected = CommitteeVote("manager", "portfolio_manager", "rejected", "no", "c" * 64)
    assert decision_pack_sha256(valid_inputs(), (vote,)) != decision_pack_sha256(valid_inputs(), (rejected,))


@pytest.mark.asyncio
async def test_portfolio_workflow_buffers_vote_delivered_before_first_workflow_task() -> None:
    workflow = PortfolioConstructionWorkflow()
    vote = CommitteeVote("manager", "portfolio_manager", "approved", "approved", "c" * 64)
    await workflow.vote(vote)
    assert workflow._pending_votes == [vote]
    assert workflow._votes == []
