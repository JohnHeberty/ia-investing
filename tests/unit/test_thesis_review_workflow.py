from __future__ import annotations

from workflows._thesis_review import (
    SpecialistResult,
    ThesisReviewInput,
    ThesisReviewResult,
    ThesisReviewWorkflow,
)


def test_specialist_result_fields():
    result = SpecialistResult(
        specialist="filing",
        verdict="positive",
        confidence=0.8,
        thesis_effect="strengthen",
        key_claims=["revenue_growth"],
        risks=["regulatory"],
        contradictions=[],
    )
    assert result.specialist == "filing"
    assert result.verdict == "positive"
    assert result.confidence == 0.8
    assert result.thesis_effect == "strengthen"
    assert "revenue_growth" in result.key_claims


def test_thesis_review_input_defaults():
    input_data = ThesisReviewInput(
        thesis_id="t1",
        thesis_version_id="v1",
        issuer_id="i1",
        data_as_of="2026-01-01",
        knowledge_cutoff="2025-12-31",
    )
    assert input_data.specialist_capabilities == ("filing", "news", "macro", "political", "critic")
    assert input_data.approval_timeout_seconds == 86_400


def test_thesis_review_workflow_detects_contradictions():
    wf = ThesisReviewWorkflow()
    results = [
        SpecialistResult(specialist="filing", verdict="pos", confidence=0.8, thesis_effect="strengthen"),
        SpecialistResult(specialist="news", verdict="neg", confidence=0.7, thesis_effect="weaken"),
        SpecialistResult(specialist="macro", verdict="pos", confidence=0.6, thesis_effect="strengthen"),
    ]
    contradictions = wf._detect_contradictions(results)
    assert "specialists_disagree_on_direction" in contradictions


def test_thesis_review_workflow_no_contradictions_when_agree():
    wf = ThesisReviewWorkflow()
    results = [
        SpecialistResult(specialist="filing", verdict="pos", confidence=0.8, thesis_effect="strengthen"),
        SpecialistResult(specialist="news", verdict="pos", confidence=0.7, thesis_effect="strengthen"),
    ]
    contradictions = wf._detect_contradictions(results)
    assert "specialists_disagree_on_direction" not in contradictions


def test_thesis_review_workflow_diff_hash_deterministic():
    wf = ThesisReviewWorkflow()
    context = {"content_sha256": "abc123"}
    results = [
        SpecialistResult(specialist="filing", verdict="pos", confidence=0.8, thesis_effect="strengthen"),
    ]
    hash1 = wf._compute_diff_hash("v1", context, results)
    hash2 = wf._compute_diff_hash("v1", context, results)
    assert hash1 == hash2
    assert len(hash1) == 64


def test_thesis_review_workflow_diff_hash_varies_with_input():
    wf = ThesisReviewWorkflow()
    context = {"content_sha256": "abc123"}
    results = [
        SpecialistResult(specialist="filing", verdict="pos", confidence=0.8, thesis_effect="strengthen"),
    ]
    hash1 = wf._compute_diff_hash("v1", context, results)
    hash2 = wf._compute_diff_hash("v2", context, results)
    assert hash1 != hash2


def test_thesis_review_workflow_initial_state():
    wf = ThesisReviewWorkflow()
    assert wf.state() == "running"


def test_thesis_review_workflow_state_after_specialists():
    wf = ThesisReviewWorkflow()
    wf._specialist_results = [
        SpecialistResult(specialist="filing", verdict="pos", confidence=0.8, thesis_effect="strengthen"),
    ]
    assert wf.state() == "awaiting_approval"


def test_thesis_review_workflow_state_after_decision():
    wf = ThesisReviewWorkflow()
    wf._decision = "approved"
    assert wf.state() == "approved"


def test_thesis_review_result_fields():
    result = ThesisReviewResult(
        thesis_id="t1",
        thesis_version_id="v1",
        status="approved",
        specialist_results=(),
        contradictions_found=(),
        diff_hash="abc123",
        decision="approved",
        approved_by="reviewer1",
    )
    assert result.thesis_id == "t1"
    assert result.status == "approved"
    assert result.approved_by == "reviewer1"


def test_thesis_review_workflow_approve_signal():
    wf = ThesisReviewWorkflow()
    import asyncio

    asyncio.get_event_loop().run_until_complete(wf.approve("reviewer1"))
    assert wf._decision == "approved"
    assert wf._reviewer == "reviewer1"


def test_thesis_review_workflow_reject_signal():
    wf = ThesisReviewWorkflow()
    import asyncio

    asyncio.get_event_loop().run_until_complete(wf.reject("reviewer1", "bad thesis"))
    assert wf._decision == "rejected"
    assert wf._reviewer == "reviewer1"


def test_thesis_review_workflow_cancel_signal():
    wf = ThesisReviewWorkflow()
    import asyncio

    asyncio.get_event_loop().run_until_complete(wf.cancel())
    assert wf._decision == "cancelled"


def test_thesis_review_workflow_signal_ignores_second_decision():
    wf = ThesisReviewWorkflow()
    import asyncio

    asyncio.get_event_loop().run_until_complete(wf.approve("reviewer1"))
    asyncio.get_event_loop().run_until_complete(wf.reject("reviewer2"))
    assert wf._decision == "approved"
    assert wf._reviewer == "reviewer1"
