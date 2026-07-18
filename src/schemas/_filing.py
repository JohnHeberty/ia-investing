from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Claim(BaseModel):
    text: str
    status: Literal["verified", "unverified"]
    source_location: str
    evidence_strength: float = Field(ge=0.0, le=1.0)


class Risk(BaseModel):
    description: str
    severity: Literal["high", "medium", "low"]
    probability: float = Field(ge=0.0, le=1.0)
    mitigation: str


class FilingReviewVerdict(BaseModel):
    verdict: Literal["positive", "negative", "neutral"]
    confidence: float = Field(ge=0.0, le=1.0)
    summary_pt: str
    materiality_score: float = Field(ge=-1.0, le=1.0)
    thesis_effect: Literal["strengthen", "weaken", "no_change"]
    claims: list[Claim]
    risks: list[Risk]
    data_gaps: list[str]
    invalidation_triggers: list[str]
