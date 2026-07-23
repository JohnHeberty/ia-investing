from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ._filing import Risk


class RiskAssessment(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    overall_risk: Literal["low", "medium", "high", "critical"]
    risk_score: float = Field(ge=0.0, le=1.0)
    top_risks: list[Risk]
    stress_test_results: dict[str, Any]
    max_drawdown_estimate: float
    volatility_estimate: float
    concentration_risks: list[str]
