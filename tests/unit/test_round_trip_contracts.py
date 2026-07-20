from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ia_investing.contracts.v1 import (
    CanonicalAnalysisV1,
    Claim,
    ClaimStatus,
    Confidence,
    DiscoveryBriefV1,
    EvidenceReference,
    Fact,
    FilingDataV1,
    FilingReviewV1,
    Inference,
    NewsAnalysisV1,
    NewsArticleV1,
    OperationAcceptedV1,
    OperationState,
    OperationStatusV1,
    ProblemDetails,
    Risk,
    ScreenFiltersV1,
)

ALL_CONTRACT_MODELS = [
    CanonicalAnalysisV1,
    Confidence,
    EvidenceReference,
    Claim,
    Fact,
    Inference,
    Risk,
    OperationStatusV1,
    OperationAcceptedV1,
    ProblemDetails,
    DiscoveryBriefV1,
    FilingReviewV1,
    FilingDataV1,
    NewsAnalysisV1,
    NewsArticleV1,
    ScreenFiltersV1,
]


def _make_analysis() -> CanonicalAnalysisV1:
    now = datetime.now(UTC)
    evidence_id = uuid4()
    claim_id = uuid4()
    return CanonicalAnalysisV1(
        analysis_id=uuid4(),
        research_case_id=uuid4(),
        agent_run_id=uuid4(),
        data_as_of=now,
        verdict="positive",
        confidence=Confidence(model=Decimal("0.8"), evidence=Decimal("0.7"), data=Decimal("0.9")),
        summary="Evidence-supported analysis.",
        claims=[
            Claim(
                claim_id=claim_id,
                text="Revenue increased.",
                status=ClaimStatus.VERIFIED,
                evidence_ids=[evidence_id],
            )
        ],
        facts=[
            Fact(
                name="revenue",
                value=Decimal("1234567890.12"),
                unit="BRL",
                as_of=now,
                evidence_id=evidence_id,
            )
        ],
        inferences=[Inference(text="Growth is material.", based_on_claim_ids=[claim_id])],
        risks=[],
        evidence=[
            EvidenceReference(
                evidence_id=evidence_id,
                source_object_id=uuid4(),
                locator="DFP 2025, DRE, line 3",
                content_hash="a" * 64,
            )
        ],
        contradictions=[],
        expires_at=now + timedelta(days=30),
    )


def test_canonical_analysis_v1_round_trip() -> None:
    """CanonicalAnalysisV1 survives JSON serialization/deserialization with Decimal precision."""
    analysis = _make_analysis()
    payload = analysis.model_dump_json()
    restored = CanonicalAnalysisV1.model_validate_json(payload)

    assert restored == analysis
    assert json.loads(payload)["facts"][0]["value"] == "1234567890.12"


def test_operation_status_v1_round_trip() -> None:
    """OperationStatusV1 preserves all Optional fields and datetime."""
    now = datetime.now(UTC)
    status = OperationStatusV1(
        operation_id=uuid4(),
        state=OperationState.RUNNING,
        created_at=now,
        updated_at=now,
        result_url="/api/v1/agent-runs/run-1",
        error_code=None,
        error_detail=None,
        metadata={"issuer": "123"},
    )
    payload = status.model_dump_json()
    restored = OperationStatusV1.model_validate_json(payload)

    assert restored == status
    assert restored.result_url == "/api/v1/agent-runs/run-1"
    assert restored.error_code is None
    assert restored.metadata == {"issuer": "123"}


def test_operation_accepted_v1_round_trip() -> None:
    """OperationAcceptedV1 default state is PENDING."""
    accepted = OperationAcceptedV1(operation_id=uuid4())

    assert accepted.state == OperationState.PENDING

    payload = accepted.model_dump_json()
    restored = OperationAcceptedV1.model_validate_json(payload)

    assert restored == accepted
    assert restored.state == OperationState.PENDING


def test_problem_details_v1_round_trip() -> None:
    """ProblemDetails round-trips correctly."""
    problem = ProblemDetails(
        type="https://example.com/errors/not-found",
        title="Not Found",
        status=404,
        detail="Issuer not found",
        instance="/api/v1/issuers/123",
    )
    payload = problem.model_dump_json()
    restored = ProblemDetails.model_validate_json(payload)

    assert restored == problem
    assert restored.status == 404


def test_discovery_brief_v1_round_trip() -> None:
    """DiscoveryBriefV1 preserves list and dict fields."""
    brief = DiscoveryBriefV1(
        issuer_id="issuer-1",
        ticker_symbol="PETR4",
        issuer_name="Petrobras",
        sector="Energy",
        market_cap=300_000_000_000.0,
        screening_score=0.85,
        anomaly_flags=["high_volatility"],
        metrics={"roe": 0.15, "debt_ratio": 0.4},
    )
    payload = brief.model_dump_json()
    restored = DiscoveryBriefV1.model_validate_json(payload)

    assert restored == brief
    assert restored.anomaly_flags == ["high_volatility"]
    assert restored.metrics == {"roe": 0.15, "debt_ratio": 0.4}


def test_filing_review_v1_round_trip() -> None:
    """FilingReviewV1 preserves Literal type constraints."""
    review = FilingReviewV1(
        issuer_id="issuer-1",
        verdict="positive",
        confidence=0.75,
        thesis_effect="strengthen",
        materiality_score=0.6,
        key_claims=["Revenue up 12%"],
        risks=["FX exposure"],
        agent_run_id="run-1",
        critic_notes="Consistent with prior filings.",
    )
    payload = review.model_dump_json()
    restored = FilingReviewV1.model_validate_json(payload)

    assert restored == review
    assert restored.verdict == "positive"
    assert restored.thesis_effect == "strengthen"


def test_filing_data_v1_round_trip() -> None:
    """FilingDataV1 preserves nested dict fields."""
    filing = FilingDataV1(
        issuer_id="issuer-1",
        issuer_name="Petrobras",
        statement_type="DRE",
        reporting_period_end="2025-12-31",
        line_items={"3.01": 50_000_000.0, "3.02": 30_000_000.0},
        metadata={"currency": "BRL", "scale": 1000},
    )
    payload = filing.model_dump_json()
    restored = FilingDataV1.model_validate_json(payload)

    assert restored == filing
    assert restored.line_items == {"3.01": 50_000_000.0, "3.02": 30_000_000.0}


def test_news_analysis_v1_round_trip() -> None:
    """NewsAnalysisV1 preserves all fields."""
    analysis = NewsAnalysisV1(
        news_item_id="news-1",
        event_type="earnings_surprise",
        description="Q4 earnings exceeded expectations.",
        materiality_score=0.9,
        direction_hint="positive",
        affected_issuers=["issuer-1", "issuer-2"],
        thesis_effects=[{"issuer_id": "issuer-1", "effect": "strengthen"}],
        agent_run_id="run-2",
    )
    payload = analysis.model_dump_json()
    restored = NewsAnalysisV1.model_validate_json(payload)

    assert restored == analysis
    assert restored.affected_issuers == ["issuer-1", "issuer-2"]
    assert restored.thesis_effects == [{"issuer_id": "issuer-1", "effect": "strengthen"}]


def test_news_article_v1_round_trip() -> None:
    """NewsArticleV1 preserves list fields."""
    article = NewsArticleV1(
        news_item_id="news-1",
        title="Petrobras reports record profit",
        body="Petrobras announced record Q4 profit...",
        url="https://example.com/news/1",
        source_name="Reuters",
        published_at="2025-07-19T10:00:00Z",
        issuer_ids=["issuer-1"],
    )
    payload = article.model_dump_json()
    restored = NewsArticleV1.model_validate_json(payload)

    assert restored == article
    assert restored.issuer_ids == ["issuer-1"]


def test_screen_filters_v1_round_trip() -> None:
    """ScreenFiltersV1 preserves default values."""
    filters = ScreenFiltersV1(
        min_market_cap=1_000_000_000.0,
        max_market_cap=500_000_000_000.0,
        sectors_include=["Energy"],
        sectors_exclude=["Finance"],
        min_volume_avg=100_000.0,
        exclude_penny_stocks=True,
    )
    payload = filters.model_dump_json()
    restored = ScreenFiltersV1.model_validate_json(payload)

    assert restored == filters
    assert restored.exclude_penny_stocks is True
    assert restored.min_market_cap == 1_000_000_000.0

    minimal = ScreenFiltersV1()
    assert minimal.exclude_penny_stocks is True
    assert minimal.sectors_include == []
    assert minimal.sectors_exclude == []


def test_all_contracts_frozen() -> None:
    """All contract models are immutable (frozen=True)."""
    for model_cls in ALL_CONTRACT_MODELS:
        config = model_cls.model_config
        assert config.get("frozen") is True, f"{model_cls.__name__} is not frozen"


def test_all_contracts_forbid_extra() -> None:
    """All contract models reject extra fields."""
    for model_cls in ALL_CONTRACT_MODELS:
        config = model_cls.model_config
        assert config.get("extra") == "forbid", f"{model_cls.__name__} does not forbid extra fields"

    with pytest.raises(ValidationError, match="Extra inputs"):
        ProblemDetails.model_validate(
            {
                "title": "err",
                "status": 500,
                "detail": "fail",
                "instance": "/x",
                "unexpected": True,
            }
        )
