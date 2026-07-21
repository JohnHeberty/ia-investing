from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
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
class PipelineConfig:
    """Raw inputs for the eligibility→optimizer→constraints pipeline."""

    portfolio_id: str
    organization_id: str
    proposed_by: str
    as_of: str
    scorecard_metrics: dict[str, float | None]
    scorecard_type: str = "industrial"
    data_quality: float = 1.0
    thesis_freshness: float = 1.0
    max_weight: float = 0.10
    min_weight: float = 0.0
    max_sector: float = 0.30
    sector_map: dict[str, str] = field(default_factory=dict)
    min_cash_weight: float = 0.0
    max_cash_weight: float = 0.0


@dataclass(frozen=True, slots=True)
class PortfolioConstructionInput:
    approval_timeout_seconds: int = 86_400
    # Pre-computed mode: provide decision_inputs directly (backward compatible)
    decision_inputs: PortfolioDecisionInputs | None = None
    # Pipeline mode: run eligibility→optimizer→constraints before committee review
    pipeline: PipelineConfig | None = None


@dataclass(frozen=True, slots=True)
class PortfolioConstructionResult:
    portfolio_id: str
    state: str
    decision_pack_sha256: str
    votes: tuple[CommitteeVote, ...]
    pipeline_summary: dict[str, object] = field(default_factory=dict)
    execution_environment: str = "paper"


@workflow.defn
class PortfolioConstructionWorkflow:
    """Chain eligibility→optimizer→constraints, then collect a four-eyes committee decision."""

    def __init__(self) -> None:
        self._votes: list[CommitteeVote] = []
        self._pending_votes: list[CommitteeVote] = []
        self._state = "validating"
        self._proposed_by = ""

    @workflow.run
    async def run(self, command: PortfolioConstructionInput) -> PortfolioConstructionResult:
        if command.approval_timeout_seconds <= 0:
            raise ValueError("approval timeout must be positive")

        pipeline_summary: dict[str, object] = {}

        if command.pipeline is not None:
            decision_inputs = await self._run_pipeline(command.pipeline, pipeline_summary)
        elif command.decision_inputs is not None:
            decision_inputs = command.decision_inputs
        else:
            raise ValueError("either decision_inputs or pipeline must be provided")

        if self._state == "rejected":
            votes = tuple(self._votes)
            return PortfolioConstructionResult(
                portfolio_id=decision_inputs.portfolio_id,
                state=self._state,
                decision_pack_sha256="",
                votes=votes,
                pipeline_summary=pipeline_summary,
            )

        validate_decision_inputs(decision_inputs)
        self._proposed_by = decision_inputs.proposed_by
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
            portfolio_id=decision_inputs.portfolio_id,
            state=self._state,
            decision_pack_sha256=decision_pack_sha256(decision_inputs, votes),
            votes=votes,
            pipeline_summary=pipeline_summary,
        )

    async def _run_pipeline(self, config: PipelineConfig, summary: dict[str, object]) -> PortfolioDecisionInputs:
        """Execute eligibility→optimizer→constraints and build PortfolioDecisionInputs."""
        self._state = "eligibility_check"

        scorecard_result: dict[str, object] = await workflow.execute_activity(
            "run_scorecard",
            args=[config.scorecard_metrics, config.scorecard_type, config.data_quality, config.thesis_freshness],
            start_to_close_timeout=timedelta(seconds=30),
        )
        summary["scorecard"] = scorecard_result

        if scorecard_result["eligibility"] != "eligible":
            self._state = "rejected"
            return PortfolioDecisionInputs(
                portfolio_id=config.portfolio_id,
                proposed_by=config.proposed_by,
                input_snapshot_sha256="",
                proposal_sha256="",
                risk_opinion="rejected",
                compliance_opinion="rejected",
                optimizer_status="skipped",
                eligible=False,
                hard_breach=False,
            )

        self._state = "optimization"
        opt_result: dict[str, object] = await workflow.execute_activity(
            "optimize_model_portfolio",
            args=[config.portfolio_id, config.organization_id, config.as_of],
            start_to_close_timeout=timedelta(seconds=45),
            heartbeat_timeout=timedelta(seconds=30),
        )
        summary["optimization"] = opt_result

        if opt_result.get("status") not in ("optimal", "optimal_inaccurate"):
            self._state = "rejected"
            return PortfolioDecisionInputs(
                portfolio_id=config.portfolio_id,
                proposed_by=config.proposed_by,
                input_snapshot_sha256=str(opt_result.get("input_sha256", "")),
                proposal_sha256="",
                risk_opinion="approved",
                compliance_opinion="approved",
                optimizer_status=str(opt_result.get("status", "failed")),
                eligible=True,
                hard_breach=False,
            )

        weights = dict(opt_result.get("weights", {}))  # type: ignore[arg-type]
        constraint_result: dict[str, object] = await workflow.execute_activity(
            "validate_proposal_constraints",
            args=[
                weights,
                config.max_weight,
                config.min_weight,
                config.max_sector,
                config.sector_map or None,
                config.min_cash_weight,
                config.max_cash_weight,
            ],
            start_to_close_timeout=timedelta(seconds=15),
        )
        summary["constraints"] = constraint_result

        hard_breach = not constraint_result["passed"]

        snapshot_hash = hashlib.sha256(
            json.dumps(
                {"portfolio_id": config.portfolio_id, "as_of": config.as_of, "weights": weights},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        proposal_hash = hashlib.sha256(
            json.dumps(
                {"snapshot": snapshot_hash, "optimizer": opt_result.get("input_sha256", "")},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

        if hard_breach:
            self._state = "rejected"

        return PortfolioDecisionInputs(
            portfolio_id=config.portfolio_id,
            proposed_by=config.proposed_by,
            input_snapshot_sha256=snapshot_hash,
            proposal_sha256=proposal_hash,
            risk_opinion="approved_with_conditions" if hard_breach else "approved",
            compliance_opinion="approved",
            optimizer_status=str(opt_result.get("status", "optimal")),
            eligible=True,
            hard_breach=hard_breach,
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
