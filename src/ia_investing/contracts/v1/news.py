from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class NewsAnalysisV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    news_item_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    description: str = Field(min_length=1)
    materiality_score: float = Field(ge=0.0, le=1.0)
    direction_hint: Literal["positive", "negative", "neutral"]
    affected_issuers: list[str] = Field(default_factory=list)
    thesis_effects: list[dict[str, Any]] = Field(default_factory=list)
    agent_run_id: str = ""


class NewsArticleV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    news_item_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    url: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    published_at: str = Field(min_length=1)
    issuer_ids: list[str] = Field(default_factory=list)
