from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ia_investing.domain.portfolio_decision import (
        CommitteeVote,
        PortfolioDecisionInputs,
        decision_pack_sha256,
        validate_committee_vote,
        validate_decision_inputs,
    )


@dataclass(frozen=True, slots=True)
class PortfolioConstructionInput:
    decision_inputs: PortfolioDecisionInputs
    approval_timeout_seconds: int


@dataclass(frozen=True, slots=True)
class PortfolioConstructionResult:
    portfolio_id: str
    state: str
    decision_pack_sha256: str
    votes: tuple[CommitteeVote, ...]
    execution_environment: str = "paper"


@workflow.defn
class PortfolioConstructionWorkflow:
    """Freeze a proposal and collect a signed, four-eyes committee decision."""

    def __init__(self) -> None:
        self._votes: list[CommitteeVote] = []
        self._pending_votes: list[CommitteeVote] = []
        self._state = "validating"
        self._proposed_by = ""

    @workflow.run
    async def run(self, command: PortfolioConstructionInput) -> PortfolioConstructionResult:
        if command.approval_timeout_seconds <= 0:
            raise ValueError("approval timeout must be positive")
        validate_decision_inputs(command.decision_inputs)
        self._proposed_by = command.decision_inputs.proposed_by
        self._state = "committee_review"
        for vote in self._pending_votes:
            self._accept_vote(vote)
        self._pending_votes.clear()
        try:
            await workflow.wait_condition(
                self._decision_ready,
                timeout=timedelta(seconds=command.approval_timeout_seconds),
            )
        except TimeoutError:
            self._state = "expired"
        if self._state == "committee_review":
            self._state = self._final_state()
        votes = tuple(self._votes)
        return PortfolioConstructionResult(
            command.decision_inputs.portfolio_id,
            self._state,
            decision_pack_sha256(command.decision_inputs, votes),
            votes,
        )

    def _decision_ready(self) -> bool:
        if self._state != "committee_review":
            return True
        if any(vote.decision == "rejected" for vote in self._votes):
            return True
        roles = {vote.role for vote in self._votes}
        return {"portfolio_manager", "risk_officer"} <= roles

    def _final_state(self) -> str:
        if any(vote.decision == "rejected" for vote in self._votes):
            return "rejected"
        if any(vote.decision == "approved_with_conditions" for vote in self._votes):
            return "conditionally_approved"
        return "approved"

    @workflow.signal
    async def vote(self, vote: CommitteeVote) -> None:
        if self._state == "validating":
            self._pending_votes.append(vote)
            return
        if self._state != "committee_review":
            return
        self._accept_vote(vote)

    def _accept_vote(self, vote: CommitteeVote) -> None:
        validate_committee_vote(
            vote,
            proposed_by=self._proposed_by,
            existing_actors=frozenset(item.actor_id for item in self._votes),
        )
        self._votes.append(vote)

    @workflow.signal
    async def cancel(self) -> None:
        if self._state == "committee_review":
            self._state = "cancelled"

    @workflow.query
    def state(self) -> str:
        return self._state
