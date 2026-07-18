from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CommitteeDecision(BaseModel):
    decision: Literal["approve", "reject", "request_more_info"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning_pt: str
    conditions: list[str]
    dissenting_opinions: list[str]
