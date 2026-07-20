from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FilingReviewV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    issuer_id: str = Field(min_length=1)
    verdict: Literal["positive", "negative", "neutral"]
    confidence: float = Field(ge=0.0, le=1.0)
    thesis_effect: Literal["strengthen", "weaken", "no_change"]
    materiality_score: float = Field(ge=0.0, le=1.0)
    key_claims: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    agent_run_id: str = ""
    critic_notes: str = ""


class FilingDataV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    issuer_id: str = Field(min_length=1)
    issuer_name: str = Field(min_length=1)
    statement_type: str = Field(min_length=1)
    reporting_period_end: str = Field(min_length=1)
    line_items: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
