from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ia_investing.domain.readiness import (
    REQUIRED_EVIDENCE_TYPES,
    REQUIRED_VOTER_ROLES,
    EvidenceStatus,
    FindingStatus,
    VoteStatus,
    evaluate_readiness_gate,
    freeze_pack_manifest,
    live_execution_is_authorized,
)


def complete_evidence(expires: datetime) -> tuple[EvidenceStatus, ...]:
    return tuple(
        EvidenceStatus(
            item, "verified", item in {"independent_security_audit", "independent_model_validation"}, expires
        )
        for item in REQUIRED_EVIDENCE_TYPES
    )


def complete_votes(vote: str = "go") -> tuple[VoteStatus, ...]:
    return tuple(VoteStatus(role, vote, True) for role in REQUIRED_VOTER_ROLES)


def test_gate_fails_closed_with_missing_external_evidence() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    result = evaluate_readiness_gate(
        at=now, pack_expires_at=now + timedelta(days=30), evidence=(), findings=(), votes=()
    )
    assert result.result == "no_go" and result.authorized_scope == "none"
    assert any("legal_opinion" in blocker for blocker in result.blockers)


def test_critical_finding_and_expired_pack_force_no_go() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    result = evaluate_readiness_gate(
        at=now,
        pack_expires_at=now,
        evidence=complete_evidence(now + timedelta(days=1)),
        findings=(FindingStatus("SEC-001", "critical", "remediating"),),
        votes=complete_votes(),
    )
    assert result.result == "no_go"
    assert "decision pack is expired" in result.blockers
    assert any("SEC-001" in blocker for blocker in result.blockers)


def test_conditional_vote_only_authorizes_remediation() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    votes = tuple(
        VoteStatus(role, "conditional_go" if role == "legal" else "go", True) for role in REQUIRED_VOTER_ROLES
    )
    result = evaluate_readiness_gate(
        at=now,
        pack_expires_at=now + timedelta(days=30),
        evidence=complete_evidence(now + timedelta(days=30)),
        findings=(),
        votes=votes,
    )
    assert result.result == "conditional_go"
    assert result.authorized_scope == "remediation_only"
    assert not live_execution_is_authorized(result)


def test_go_authorizes_only_a_future_plan_never_live_execution() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    result = evaluate_readiness_gate(
        at=now,
        pack_expires_at=now + timedelta(days=30),
        evidence=complete_evidence(now + timedelta(days=30)),
        findings=(),
        votes=complete_votes(),
    )
    assert result.result == "go"
    assert result.authorized_scope == "future_live_planning"
    assert not live_execution_is_authorized(result)


def test_pack_hash_is_canonical_and_changes_with_manifest() -> None:
    first, canonical = freeze_pack_manifest({"b": [2], "a": 1})
    second, _ = freeze_pack_manifest({"a": 1, "b": [2]})
    changed, _ = freeze_pack_manifest({"a": 2, "b": [2]})
    assert first == second and first != changed
    assert list(canonical) == ["a", "b"]
