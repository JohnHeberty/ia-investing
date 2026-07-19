from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class PortfolioDecisionInputs:
    portfolio_id: str
    proposed_by: str
    input_snapshot_sha256: str
    proposal_sha256: str
    risk_opinion: str
    compliance_opinion: str
    optimizer_status: str
    eligible: bool
    hard_breach: bool


@dataclass(frozen=True, slots=True)
class CommitteeVote:
    actor_id: str
    role: str
    decision: str
    rationale: str
    signature_sha256: str
    conditions: tuple[str, ...] = ()


def validate_decision_inputs(inputs: PortfolioDecisionInputs) -> None:
    hashes = (inputs.input_snapshot_sha256, inputs.proposal_sha256)
    if any(len(value) != 64 or any(character not in "0123456789abcdef" for character in value) for value in hashes):
        raise ValueError("decision pack hashes must be lowercase SHA-256")
    if not inputs.eligible or inputs.hard_breach:
        raise ValueError("portfolio proposal is ineligible or has a hard risk breach")
    if inputs.optimizer_status not in {"optimal", "optimal_inaccurate"}:
        raise ValueError("optimizer did not produce a valid proposal")
    if inputs.risk_opinion not in {"approved", "approved_with_conditions"}:
        raise ValueError("risk opinion blocks the proposal")
    if inputs.compliance_opinion != "approved":
        raise ValueError("compliance opinion blocks the proposal")


def validate_committee_vote(vote: CommitteeVote, *, proposed_by: str, existing_actors: frozenset[str]) -> None:
    if vote.actor_id == proposed_by:
        raise PermissionError("proposal author cannot approve the proposal")
    if vote.actor_id in existing_actors:
        raise ValueError("committee actor has already voted")
    if vote.role not in {"portfolio_manager", "risk_officer", "compliance_officer"}:
        raise ValueError("committee vote role is not authorized")
    if vote.decision not in {"approved", "approved_with_conditions", "rejected"}:
        raise ValueError("invalid committee decision")
    if not vote.rationale.strip() or len(vote.signature_sha256) != 64:
        raise ValueError("committee vote requires rationale and signature hash")
    if vote.decision == "approved_with_conditions" and not vote.conditions:
        raise ValueError("conditional approval requires explicit conditions")


def decision_pack_sha256(inputs: PortfolioDecisionInputs, votes: tuple[CommitteeVote, ...]) -> str:
    payload = json.dumps(
        {"inputs": asdict(inputs), "votes": [asdict(vote) for vote in votes]},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()
