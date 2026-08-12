from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class NewsAnalysis(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    verdict: Literal["positive", "negative", "neutral", "mixed"]
    confidence: float = Field(ge=0.0, le=1.0)
    summary_pt: str
    materiality_score: float = Field(ge=-1.0, le=1.0)
    thesis_effect: Literal["strengthen", "weaken", "no_change"]
    event_type: Literal[
        "earnings",
        "guidance",
        "ma",
        "regulation",
        "dividend",
        "governance",
        "market",
        "sector",
        "other",
    ]
    affected_metrics: list[str]
    time_horizon: Literal["immediate", "short_term", "medium_term", "long_term"]
    key_claims: list[str]
    affected_issuers: list[dict[str, Any]] = Field(default_factory=list)
