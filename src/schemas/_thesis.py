from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ThesisVerdict(BaseModel):
    action: Literal["buy", "sell", "hold"]
    confidence: float = Field(ge=0.0, le=1.0)
    target_price: float | None = None
    current_price: float
    reasoning_pt: str
    supporting_assessments: list[str]
    opposing_arguments: list[str]
    review_deadline: str
    invalidation_triggers: list[str]
