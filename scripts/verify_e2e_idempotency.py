"""Exercise E2E idempotency across contracts, operations, and activities."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

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
    Risk,
    ScreenFiltersV1,
)
from ia_investing.orchestration.activities.notifications import publish_event
from ia_investing.orchestration.activities.research_mock import run_filing_analyst, run_news_analyst

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CHECKS_PASSED = 0
_CHECKS_FAILED = 0
_VERBOSE = False


def _check(label: str, passed: bool) -> None:
    global _CHECKS_PASSED, _CHECKS_FAILED
    if passed:
        _CHECKS_PASSED += 1
        if _VERBOSE:
            print(f"  ✓ {label}")
    else:
        _CHECKS_FAILED += 1
        print(f"  ✗ {label}")


def _uuid() -> str:
    return str(uuid4())


def _json_roundtrip(obj: Any) -> Any:
    data = obj.model_dump(mode="json")
    return obj.__class__.model_validate_json(json.dumps(data))


# ---------------------------------------------------------------------------
# 1. Contract round-trip idempotency
# ---------------------------------------------------------------------------


def _build_operation_accepted() -> OperationAcceptedV1:
    return OperationAcceptedV1(operation_id=uuid4())


def _build_discovery_brief() -> DiscoveryBriefV1:
    return DiscoveryBriefV1(
        issuer_id=_uuid(),
        ticker_symbol="PETR4",
        issuer_name="Petrobras PN",
        sector="Energy",
        market_cap=1_000_000_000.0,
        screening_score=0.85,
        anomaly_flags=["low_volume"],
        metrics={"pe_ratio": 8.5},
    )


def _build_screen_filters() -> ScreenFiltersV1:
    return ScreenFiltersV1(
        min_market_cap=1_000_000.0,
        max_market_cap=1_000_000_000_000.0,
        sectors_include=["Energy", "Finance"],
        sectors_exclude=[],
        min_volume_avg=100_000.0,
        exclude_penny_stocks=True,
    )


def _build_filing_review() -> FilingReviewV1:
    return FilingReviewV1(
        issuer_id="PETR4",
        verdict="positive",
        confidence=0.75,
        thesis_effect="strengthen",
        materiality_score=0.9,
        key_claims=["Revenue growth"],
        risks=["Regulatory change"],
        agent_run_id=_uuid(),
        critic_notes="Solid quarter.",
    )


def _build_filing_data() -> FilingDataV1:
    return FilingDataV1(
        issuer_id="PETR4",
        issuer_name="Petrobras",
        statement_type="BPA",
        reporting_period_end="2025-12-31",
        line_items={"cash": 50_000_000.0},
        metadata={"source": "CVM"},
    )


def _build_news_analysis() -> NewsAnalysisV1:
    return NewsAnalysisV1(
        news_item_id=_uuid(),
        event_type="earnings_release",
        description="Q4 2025 earnings beat expectations.",
        materiality_score=0.8,
        direction_hint="positive",
        affected_issuers=["PETR4"],
        thesis_effects=[{"issuer_id": "PETR4", "effect": "strengthen"}],
        agent_run_id=_uuid(),
    )


def _build_news_article() -> NewsArticleV1:
    return NewsArticleV1(
        news_item_id=_uuid(),
        title="Petrobras reports record profit",
        body="Petrobras announced record net income for Q4 2025.",
        url="https://example.com/news/1",
        source_name="Example News",
        published_at="2026-01-15T10:00:00Z",
        issuer_ids=["PETR4"],
    )


def _build_canonical_analysis() -> CanonicalAnalysisV1:
    evidence_id = uuid4()
    source_object_id = uuid4()
    claim_id = uuid4()
    now = datetime(2026, 7, 19, 12, tzinfo=UTC)
    return CanonicalAnalysisV1(
        analysis_id=uuid4(),
        research_case_id=uuid4(),
        agent_run_id=uuid4(),
        data_as_of=now,
        verdict="positive",
        confidence=Confidence(model=Decimal("0.80"), evidence=Decimal("0.75"), data=Decimal("0.90")),
        summary="Strong quarterly performance.",
        claims=[
            Claim(
                claim_id=claim_id,
                text="Revenue exceeded forecasts.",
                status=ClaimStatus.VERIFIED,
                evidence_ids=[evidence_id],
            )
        ],
        facts=[
            Fact(
                name="net_revenue",
                value=Decimal("120000000"),
                unit="BRL",
                as_of=now,
                evidence_id=evidence_id,
            )
        ],
        inferences=[Inference(text="Bullish outlook.", based_on_claim_ids=[claim_id])],
        risks=[
            Risk(
                description="Oil price volatility",
                probability=Decimal("0.40"),
                impact="medium",
                evidence_ids=[evidence_id],
            )
        ],
        evidence=[
            EvidenceReference(
                evidence_id=evidence_id,
                source_object_id=source_object_id,
                locator="cvm://dfp/2025/q4",
                content_hash="a" * 64,
            )
        ],
        contradictions=[],
        expires_at=datetime(2026, 8, 19, 12, tzinfo=UTC),
    )


_CONTRACT_BUILDERS: list[tuple[str, Any]] = [
    ("OperationAcceptedV1", _build_operation_accepted),
    ("DiscoveryBriefV1", _build_discovery_brief),
    ("ScreenFiltersV1", _build_screen_filters),
    ("FilingReviewV1", _build_filing_review),
    ("FilingDataV1", _build_filing_data),
    ("NewsAnalysisV1", _build_news_analysis),
    ("NewsArticleV1", _build_news_article),
    ("CanonicalAnalysisV1", _build_canonical_analysis),
]


def check_contract_roundtrip() -> None:
    print("[contract-roundtrip]")
    for name, builder in _CONTRACT_BUILDERS:
        original = builder()
        restored = _json_roundtrip(original)
        _check(
            f"{name}-idempotent",
            original == restored,
        )


# ---------------------------------------------------------------------------
# 2. Operation idempotency
# ---------------------------------------------------------------------------


def check_operation_idempotency() -> None:
    print("[operation-idempotency]")
    op_id = uuid4()
    first = OperationAcceptedV1(operation_id=op_id)
    second = OperationAcceptedV1(operation_id=op_id)
    _check("operation-idempotent", first.model_dump(mode="json") == second.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# 3. Activity output idempotency
# ---------------------------------------------------------------------------


def check_activity_idempotency() -> None:
    print("[activity-idempotency]")

    event_type = "filing.processed"
    payload: dict[str, Any] = {"issuer_id": "PETR4", "verdict": "positive"}
    first_event = publish_event(event_type, payload)
    second_event = publish_event(event_type, payload)
    _check("publish_event-idempotent", first_event == second_event)

    first_filing = run_filing_analyst(
        issuer_id="PETR4",
        issuer_name="Petrobras",
        line_items={"cash": 50_000_000},
        metrics={"current_ratio": 1.5},
    )
    second_filing = run_filing_analyst(
        issuer_id="PETR4",
        issuer_name="Petrobras",
        line_items={"cash": 50_000_000},
        metrics={"current_ratio": 1.5},
    )
    _check("run_filing_analyst-idempotent", first_filing == second_filing)

    first_news = run_news_analyst(
        news_item_id="news-001",
        title="Earnings beat",
        body="Q4 results beat consensus.",
        url="https://example.com/1",
    )
    second_news = run_news_analyst(
        news_item_id="news-001",
        title="Earnings beat",
        body="Q4 results beat consensus.",
        url="https://example.com/1",
    )
    _check("run_news_analyst-idempotent", first_news == second_news)


# ---------------------------------------------------------------------------
# 4. Contract version consistency
# ---------------------------------------------------------------------------


def check_version_consistency() -> None:
    print("[contract-version-consistency]")
    for name, builder in _CONTRACT_BUILDERS:
        instance = builder()
        has_version = getattr(instance, "schema_version", None) == "1.0"
        _check(f"{name}-schema-version", has_version)
        _check(f"{name}-extra-forbid", instance.model_config.get("extra") == "forbid")
        _check(f"{name}-frozen", instance.model_config.get("frozen") is True)


# ---------------------------------------------------------------------------
# 5. Main
# ---------------------------------------------------------------------------


def main() -> None:
    global _VERBOSE

    parser = argparse.ArgumentParser(description="Verify E2E idempotency guarantees.")
    parser.add_argument("--verbose", action="store_true", help="Print details for each check.")
    args = parser.parse_args()
    _VERBOSE = args.verbose

    check_contract_roundtrip()
    check_operation_idempotency()
    check_activity_idempotency()
    check_version_consistency()

    total = _CHECKS_PASSED + _CHECKS_FAILED
    print(f"\nsummary passed={_CHECKS_PASSED} failed={_CHECKS_FAILED} total={total}")
    if _CHECKS_FAILED:
        print("e2e-idempotency=FAIL")
        raise SystemExit(1)
    print("e2e-idempotency=PASS")


if __name__ == "__main__":
    main()
