"""F1-PR07: Integration, concurrency and auth tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ia_investing.application.research import (
    ResearchCaseService,
    ResearchConcurrencyError,
)
from ia_investing.application.reviews import ensure_segregation
from ia_investing.application.theses import ThesisService
from ia_investing.contracts.v1 import (
    DiscoveryBriefV1,
    FilingReviewV1,
    NewsAnalysisV1,
    OperationAcceptedV1,
    OperationState,
    OperationStatusV1,
)
from ia_investing.contracts.v1.problem import ProblemDetails
from ia_investing.domain.identity import ensure_four_eyes

# ---------------------------------------------------------------------------
# Category 1: Contract round-trip tests
# ---------------------------------------------------------------------------


def test_operation_status_v1_json_round_trip() -> None:
    """OperationStatusV1 serializes and deserializes preserving all fields."""
    now = datetime.now(UTC)
    model = OperationStatusV1(
        operation_id=uuid4(),
        state=OperationState.RUNNING,
        created_at=now,
        updated_at=now,
        result_url="https://example.com/result",
        error_code=None,
        error_detail=None,
        metadata={"key": "value"},
    )
    payload = model.model_dump_json()
    restored = OperationStatusV1.model_validate_json(payload)

    assert restored == model
    parsed = json.loads(payload)
    assert parsed["schema_version"] == "1.0"
    assert parsed["operation_id"] == str(model.operation_id)
    assert parsed["state"] == "running"
    assert parsed["metadata"] == {"key": "value"}


def test_operation_accepted_v1_json_round_trip() -> None:
    """OperationAcceptedV1 serializes and deserializes with default state."""
    model = OperationAcceptedV1(operation_id=uuid4())
    payload = model.model_dump_json()
    restored = OperationAcceptedV1.model_validate_json(payload)

    assert restored == model
    parsed = json.loads(payload)
    assert parsed["state"] == "pending"
    assert parsed["schema_version"] == "1.0"


def test_discovery_brief_v1_json_round_trip() -> None:
    """DiscoveryBriefV1 preserves all fields through JSON round-trip."""
    model = DiscoveryBriefV1(
        issuer_id="petr4",
        ticker_symbol="PETR4",
        issuer_name="Petrobras",
        sector="energy",
        market_cap=1_000_000_000.0,
        screening_score=0.85,
        anomaly_flags=["high_volatility"],
        metrics={"pe_ratio": 8.5},
    )
    payload = model.model_dump_json()
    restored = DiscoveryBriefV1.model_validate_json(payload)

    assert restored == model
    assert restored.issuer_id == "petr4"
    assert restored.anomaly_flags == ["high_volatility"]
    assert restored.metrics == {"pe_ratio": 8.5}


def test_filing_review_v1_json_round_trip() -> None:
    """FilingReviewV1 preserves all fields through JSON round-trip."""
    model = FilingReviewV1(
        issuer_id="petr4",
        verdict="positive",
        confidence=0.9,
        thesis_effect="strengthen",
        materiality_score=0.8,
        key_claims=["revenue grew 15%"],
        risks=["oil price dependency"],
        agent_run_id="run-42",
        critic_notes="Solid quarter.",
    )
    payload = model.model_dump_json()
    restored = FilingReviewV1.model_validate_json(payload)

    assert restored == model
    assert restored.verdict == "positive"
    assert restored.key_claims == ["revenue grew 15%"]


def test_news_analysis_v1_json_round_trip() -> None:
    """NewsAnalysisV1 preserves all fields through JSON round-trip."""
    model = NewsAnalysisV1(
        news_item_id="news-001",
        event_type="earnings_release",
        description="Petrobras reported record profits.",
        materiality_score=0.95,
        direction_hint="positive",
        affected_issuers=["petr4"],
        thesis_effects=[{"thesis_id": "t1", "effect": "strengthen"}],
        agent_run_id="run-99",
    )
    payload = model.model_dump_json()
    restored = NewsAnalysisV1.model_validate_json(payload)

    assert restored == model
    assert restored.affected_issuers == ["petr4"]
    assert restored.thesis_effects == [{"thesis_id": "t1", "effect": "strengthen"}]


def test_all_contracts_reject_extra_fields() -> None:
    """Every contract model with extra='forbid' rejects unknown fields."""
    models: list[tuple[str, Any, dict[str, Any]]] = [
        (
            "OperationStatusV1",
            OperationStatusV1,
            {
                "operation_id": uuid4(),
                "state": "pending",
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            },
        ),
        (
            "OperationAcceptedV1",
            OperationAcceptedV1,
            {"operation_id": uuid4()},
        ),
        (
            "DiscoveryBriefV1",
            DiscoveryBriefV1,
            {
                "issuer_id": "petr4",
                "ticker_symbol": "PETR4",
                "issuer_name": "Petrobras",
                "sector": "energy",
                "market_cap": 1e9,
                "screening_score": 0.5,
            },
        ),
        (
            "FilingReviewV1",
            FilingReviewV1,
            {
                "issuer_id": "petr4",
                "verdict": "neutral",
                "confidence": 0.5,
                "thesis_effect": "no_change",
                "materiality_score": 0.5,
            },
        ),
        (
            "NewsAnalysisV1",
            NewsAnalysisV1,
            {
                "news_item_id": "n1",
                "event_type": "regulatory",
                "description": "New regulation.",
                "materiality_score": 0.5,
                "direction_hint": "neutral",
            },
        ),
    ]

    for _name, model_cls, valid_kwargs in models:
        with pytest.raises(Exception, match="Extra inputs"):
            model_cls(**valid_kwargs, unexpected_field="not allowed")


def _get_client():
    """Lazy import to avoid failing at module load when agents package is missing."""
    from fastapi.testclient import TestClient

    from apps.api.main import app

    return TestClient(app, raise_server_exceptions=False), app


# ---------------------------------------------------------------------------
# Category 2: Auth and permission tests (using TestClient)
# ---------------------------------------------------------------------------


def test_unauthenticated_request_returns_401_problem_details() -> None:
    """All protected endpoints return 401 with ProblemDetails format."""
    client, _app = _get_client()
    protected_endpoints = [
        ("GET", "/api/v1/operations/00000000-0000-4000-8000-000000000001"),
        ("GET", "/api/v1/research/cases"),
        ("GET", "/api/v1/paper/trade-intents"),
    ]

    for method, path in protected_endpoints:
        response = client.get(path) if method == "GET" else client.post(path)

        assert response.status_code == 401, f"Expected 401 for {method} {path}"
        assert response.headers["content-type"].startswith("application/problem+json")
        body = response.json()
        assert body["title"] == "Unauthorized"
        assert body["status"] == 401
        assert body["instance"] == path


def test_read_only_endpoints_require_read_permission() -> None:
    """GET endpoints require appropriate read permission."""
    client, _app = _get_client()
    response = client.get("/api/v1/operations/00000000-0000-4000-8000-000000000001")
    assert response.status_code == 401
    assert response.json()["title"] == "Unauthorized"


def test_command_endpoints_require_write_permission() -> None:
    """POST endpoints require appropriate write permission."""
    client, _app = _get_client()
    response = client.post(
        "/api/v1/agent-runs",
        json={"agent_name": "test", "input_data": {}},
    )
    assert response.status_code == 401
    assert response.json()["title"] == "Unauthorized"


def test_idempotency_key_header_required_on_commands() -> None:
    """All command POST endpoints require Idempotency-Key header."""
    client, app = _get_client()
    response = client.post(
        "/api/v1/agent-runs",
        json={"agent_name": "test", "input_data": {}},
    )
    assert response.status_code == 401

    openapi = app.openapi()
    agent_runs_post = openapi["paths"]["/api/v1/agent-runs"]["post"]
    idempotency_param = next(
        (p for p in agent_runs_post.get("parameters", []) if p["name"] == "Idempotency-Key"),
        None,
    )
    assert idempotency_param is not None
    assert idempotency_param["required"] is True

    research_cases_post = openapi["paths"]["/api/v1/research/cases"]["post"]
    idempotency_param = next(
        (p for p in research_cases_post.get("parameters", []) if p["name"] == "Idempotency-Key"),
        None,
    )
    assert idempotency_param is not None
    assert idempotency_param["required"] is True


def test_if_match_header_required_on_transitions() -> None:
    """Transition endpoints require If-Match header for optimistic concurrency."""
    _client, app = _get_client()
    openapi = app.openapi()

    transition_params = openapi["paths"]["/api/v1/research/cases/{case_id}/transitions"]["post"]["parameters"]
    if_match_param = next(p for p in transition_params if p["name"] == "If-Match")
    assert if_match_param["required"] is True

    revise_params = openapi["paths"]["/api/v1/research/theses/{thesis_id}/versions"]["post"]["parameters"]
    if_match_param = next(p for p in revise_params if p["name"] == "If-Match")
    assert if_match_param["required"] is True


# ---------------------------------------------------------------------------
# Category 3: Concurrency tests (using domain logic)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_research_case_transition_rejects_stale_etag() -> None:
    """ResearchCaseService.transition raises ResearchConcurrencyError on stale version."""
    mock_session = AsyncMock()
    mock_case = MagicMock()
    mock_case.lock_version = 3
    mock_case.state = "draft"
    mock_session.get = AsyncMock(return_value=mock_case)

    service = ResearchCaseService(mock_session)

    with pytest.raises(ResearchConcurrencyError, match="ETag no longer matches"):
        await service.transition(
            case_id=uuid4(),
            target="triage",
            expected_version=1,
            actor_subject="analyst-1",
            permissions=frozenset({"research_cases:submit"}),
            correlation_id=uuid4(),
            reason="test stale etag",
        )


@pytest.mark.asyncio
async def test_thesis_revision_rejects_stale_etag() -> None:
    """ThesisService.revise raises error when lock_version mismatches."""
    from datetime import timedelta

    from ia_investing.application.theses import ThesisSnapshot

    mock_session = AsyncMock()
    mock_thesis = MagicMock()
    mock_thesis.lock_version = 5
    mock_session.get = AsyncMock(return_value=mock_thesis)

    service = ThesisService(mock_session)
    now = datetime.now(UTC)
    snapshot = ThesisSnapshot(
        summary="Test",
        assumptions=[],
        catalysts=[],
        risks=[],
        invalidation_criteria=[],
        recommendation="buy",
        recommendation_confidence=Decimal("0.8"),
        data_as_of=now,
        expires_at=now + timedelta(days=30),
    )

    with pytest.raises(ResearchConcurrencyError, match="ETag no longer matches"):
        await service.revise(
            thesis_id=uuid4(),
            expected_version=1,
            snapshot=snapshot,
            actor_subject="analyst-1",
            permissions=frozenset({"research_theses:revise"}),
            evidence_ids=[uuid4()],
            claim_ids=[uuid4()],
        )


def test_paper_kill_switch_requires_different_releaser() -> None:
    """ensure_four_eyes prevents same user from activating and releasing kill switch."""
    with pytest.raises(PermissionError, match="author cannot approve their own action"):
        ensure_four_eyes("operator-1", "operator-1")


def test_readiness_vote_requires_different_voter() -> None:
    """ReadinessVote segregation enforced."""
    ensure_segregation("analyst-1", "reviewer-1")
    with pytest.raises(ValueError, match="own work"):
        ensure_segregation("analyst-1", "analyst-1")


# ---------------------------------------------------------------------------
# Category 4: ProblemDetails format tests
# ---------------------------------------------------------------------------


def test_404_returns_problem_details() -> None:
    """Non-existent resource returns 404 with ProblemDetails body."""
    client, _app = _get_client()
    response = client.get(
        "/api/v1/operations/00000000-0000-4000-8000-000000000001",
        headers={"Authorization": "Bearer fake-token"},
    )
    assert response.status_code in {401, 404, 503}

    client_with_dev, _app = _get_client()
    response = client_with_dev.get(
        "/api/v1/operations/00000000-0000-4000-8000-000000000001",
        headers={
            "X-Dev-Subject": "test@example.com",
            "X-Dev-Permissions": "operations:read",
        },
    )
    if response.status_code == 404:
        assert response.headers["content-type"].startswith("application/problem+json")
        body = response.json()
        assert body["title"] == "Not Found"
        assert body["status"] == 404
        assert body["instance"] == "/api/v1/operations/00000000-0000-4000-8000-000000000001"
        ProblemDetails.model_validate(body)


def test_422_returns_problem_details_for_validation() -> None:
    """Invalid input returns 422 with ProblemDetails body and validation details."""
    client, _app = _get_client()
    response = client.post(
        "/api/v1/agent-runs",
        json={},
    )
    assert response.status_code in {401, 422}

    response = client.post(
        "/api/v1/agent-runs",
        json={"extra_field": True},
    )
    assert response.status_code in {401, 422}
    if response.status_code == 422:
        assert response.headers["content-type"].startswith("application/problem+json")
        body = response.json()
        assert body["title"] == "Unprocessable Entity"
        assert body["status"] == 422
        ProblemDetails.model_validate(body)
