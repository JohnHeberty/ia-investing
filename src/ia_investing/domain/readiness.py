from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

REQUIRED_VOTER_ROLES = frozenset({"legal", "security", "risk", "compliance", "operations", "data", "investments"})
REQUIRED_EVIDENCE_TYPES = frozenset(
    {
        "legal_opinion",
        "data_license_review",
        "independent_security_audit",
        "restore_drill",
        "kill_switch_drill",
        "independent_model_validation",
        "paper_operating_record",
        "control_matrix",
    }
)


@dataclass(frozen=True, slots=True)
class EvidenceStatus:
    evidence_type: str
    status: str
    independent: bool
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class FindingStatus:
    finding_key: str
    severity: str
    status: str
    exception_expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class VoteStatus:
    role: str
    vote: str
    conflicts_disclosed: bool


@dataclass(frozen=True, slots=True)
class GateEvaluation:
    result: str
    authorized_scope: str
    blockers: tuple[str, ...]
    conditions: tuple[str, ...]


def evaluate_readiness_gate(
    *,
    at: datetime,
    pack_expires_at: datetime,
    evidence: tuple[EvidenceStatus, ...],
    findings: tuple[FindingStatus, ...],
    votes: tuple[VoteStatus, ...],
) -> GateEvaluation:
    if at.tzinfo is None or pack_expires_at.tzinfo is None:
        raise ValueError("gate timestamps must include timezone information")
    blockers: list[str] = []
    if pack_expires_at <= at:
        blockers.append("decision pack is expired")
    verified_by_type = {
        item.evidence_type: item
        for item in evidence
        if item.status == "verified" and (item.expires_at is None or item.expires_at > at)
    }
    for evidence_type in sorted(REQUIRED_EVIDENCE_TYPES - verified_by_type.keys()):
        blockers.append(f"missing verified evidence: {evidence_type}")
    for evidence_type in ("independent_security_audit", "independent_model_validation"):
        item = verified_by_type.get(evidence_type)
        if item is not None and not item.independent:
            blockers.append(f"evidence must be independent: {evidence_type}")
    for finding in findings:
        exception_valid = finding.exception_expires_at is not None and finding.exception_expires_at > at
        if finding.severity == "critical" and finding.status != "closed":
            blockers.append(f"critical finding is open: {finding.finding_key}")
        elif finding.severity == "high" and finding.status not in {"closed", "risk_accepted"} and not exception_valid:
            blockers.append(f"high finding lacks valid disposition: {finding.finding_key}")
    votes_by_role = {vote.role: vote for vote in votes}
    for role in sorted(REQUIRED_VOTER_ROLES - votes_by_role.keys()):
        blockers.append(f"missing required vote: {role}")
    for vote in votes:
        if not vote.conflicts_disclosed:
            blockers.append(f"conflicts were not disclosed by role: {vote.role}")
        if vote.vote == "no_go":
            blockers.append(f"no-go vote: {vote.role}")
    if blockers:
        return GateEvaluation("no_go", "none", tuple(blockers), ())
    conditions = tuple(f"conditional vote: {vote.role}" for vote in votes if vote.vote == "conditional_go")
    if conditions:
        return GateEvaluation("conditional_go", "remediation_only", (), conditions)
    return GateEvaluation("go", "future_live_planning", (), ())


def freeze_pack_manifest(manifest: dict[str, object]) -> tuple[str, dict[str, object]]:
    canonical = json.loads(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return digest, canonical


def live_execution_is_authorized(evaluation: GateEvaluation) -> bool:
    # Even a successful phase-9 decision authorizes planning only.
    return False
