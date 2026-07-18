from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class NewsAnalysis(BaseModel):
    verdict: Literal["positive", "negative", "neutral", "mixed"]
    confidence: float = Field(ge=0.0, le=1.0)
    summary_pt: str
    materiality_score: float = Field(ge=-1.0, le=1.0)
    thesis_effect: Literal["strengthen", "weaken", "no_change"]
    event_type: str
    affected_metrics: list[str]
    time_horizon: str
    key_claims: list[str]
