from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DiscoveryBriefV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    issuer_id: str = Field(min_length=1)
    ticker_symbol: str = Field(min_length=1)
    issuer_name: str = Field(min_length=1)
    sector: str = Field(min_length=1)
    market_cap: float = Field(ge=0)
    screening_score: float
    anomaly_flags: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class ScreenFiltersV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    min_market_cap: float = 0.0
    max_market_cap: float = float("inf")
    sectors_include: list[str] = Field(default_factory=list)
    sectors_exclude: list[str] = Field(default_factory=list)
    min_volume_avg: float = 0.0
    exclude_penny_stocks: bool = True
