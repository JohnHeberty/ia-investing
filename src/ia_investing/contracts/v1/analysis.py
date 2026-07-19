from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

ConfidenceScore = Annotated[Decimal, Field(ge=Decimal("0"), le=Decimal("1"))]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AnalysisVerdict(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ClaimStatus(StrEnum):
    VERIFIED = "verified"
    CONTRADICTED = "contradicted"
    UNVERIFIED = "unverified"


class Confidence(ContractModel):
    model: ConfidenceScore
    evidence: ConfidenceScore
    data: ConfidenceScore


class EvidenceReference(ContractModel):
    evidence_id: UUID
    source_object_id: UUID
    locator: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class Claim(ContractModel):
    claim_id: UUID
    text: str = Field(min_length=1)
    status: ClaimStatus
    evidence_ids: list[UUID] = Field(min_length=1)


class Fact(ContractModel):
    name: str = Field(min_length=1)
    value: Decimal
    unit: str = Field(min_length=1)
    as_of: AwareDatetime
    evidence_id: UUID


class Inference(ContractModel):
    text: str = Field(min_length=1)
    based_on_claim_ids: list[UUID] = Field(min_length=1)


class Risk(ContractModel):
    description: str = Field(min_length=1)
    probability: ConfidenceScore
    impact: Literal["low", "medium", "high", "critical"]
    evidence_ids: list[UUID]


class CanonicalAnalysisV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    analysis_id: UUID
    research_case_id: UUID
    agent_run_id: UUID
    data_as_of: AwareDatetime
    verdict: AnalysisVerdict
    confidence: Confidence
    summary: str = Field(min_length=1)
    claims: list[Claim]
    facts: list[Fact]
    inferences: list[Inference]
    risks: list[Risk]
    evidence: list[EvidenceReference]
    contradictions: list[str]
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def validate_references_and_expiry(self) -> CanonicalAnalysisV1:
        if self.expires_at <= self.data_as_of:
            raise ValueError("expires_at must be later than data_as_of")

        evidence_ids = {item.evidence_id for item in self.evidence}
        referenced_evidence = {evidence_id for claim in self.claims for evidence_id in claim.evidence_ids}
        referenced_evidence.update(fact.evidence_id for fact in self.facts)
        referenced_evidence.update(evidence_id for risk in self.risks for evidence_id in risk.evidence_ids)
        missing_evidence = referenced_evidence - evidence_ids
        if missing_evidence:
            raise ValueError("references unknown evidence IDs")

        claim_ids = {claim.claim_id for claim in self.claims}
        referenced_claims = {claim_id for inference in self.inferences for claim_id in inference.based_on_claim_ids}
        if referenced_claims - claim_ids:
            raise ValueError("inferences reference unknown claim IDs")
        return self
