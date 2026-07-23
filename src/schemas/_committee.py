from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CommitteeDecision(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    decision: Literal["approve", "reject", "request_more_info"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning_pt: str
    conditions: list[str]
    dissenting_opinions: list[str]
