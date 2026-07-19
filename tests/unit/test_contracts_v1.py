from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ia_investing.contracts.v1 import (
    CanonicalAnalysisV1,
    Claim,
    ClaimStatus,
    Confidence,
    EvidenceReference,
    Fact,
    Inference,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "contracts" / "v1"


def make_analysis() -> CanonicalAnalysisV1:
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


def test_canonical_analysis_json_round_trip_preserves_decimal() -> None:
    analysis = make_analysis()

    payload = analysis.model_dump_json()
    restored = CanonicalAnalysisV1.model_validate_json(payload)

    assert restored == analysis
    assert json.loads(payload)["facts"][0]["value"] == "1234567890.12"


def test_contract_rejects_naive_dates() -> None:
    payload = make_analysis().model_dump()
    payload["data_as_of"] = datetime.now()

    with pytest.raises(ValidationError):
        CanonicalAnalysisV1.model_validate(payload)


def test_contract_rejects_unknown_evidence_reference() -> None:
    payload = make_analysis().model_dump()
    payload["claims"][0]["evidence_ids"] = [uuid4()]

    with pytest.raises(ValidationError, match="unknown evidence"):
        CanonicalAnalysisV1.model_validate(payload)


def test_contract_rejects_silent_extra_fields() -> None:
    payload = make_analysis().model_dump()
    payload["unexpected"] = "not allowed"

    with pytest.raises(ValidationError, match="Extra inputs"):
        CanonicalAnalysisV1.model_validate(payload)


def test_published_contract_fixtures() -> None:
    valid = CanonicalAnalysisV1.model_validate_json((FIXTURES / "analysis-valid.json").read_text("utf-8"))
    assert valid.schema_version == "1.0"

    with pytest.raises(ValidationError):
        CanonicalAnalysisV1.model_validate_json((FIXTURES / "analysis-invalid.json").read_text("utf-8"))
