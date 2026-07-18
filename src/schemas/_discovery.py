from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DiscoveryBrief(BaseModel):
    ticker: str
    issuer_name: str
    sector: str
    market_cap: float
    pe_ttm: float | None = None
    dividend_yield: float | None = None
    discovery_reason: str
    initial_score: float = Field(ge=0.0, le=1.0)
    anomaly_type: str
    recommendation: Literal["research", "monitor", "skip"]
