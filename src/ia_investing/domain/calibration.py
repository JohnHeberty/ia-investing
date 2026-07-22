from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ComponentName(StrEnum):
    POLITICAL_INTELLIGENCE = "political_intelligence"
    PORTFOLIO_RANKING = "portfolio_ranking"
    THESIS_ANALYSIS = "thesis_analysis"
    RISK_ASSESSMENT = "risk_assessment"
    MARKET_PREDICTION = "market_prediction"


class CalibrationStatus(StrEnum):
    PENDING = "pending"
    CALIBRATED = "calibrated"
    DRIFTED = "drifted"
    INVALID = "invalid"


class CalibrationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    component: ComponentName
    inputs_hash: str = Field(min_length=64, max_length=64)
    output_summary: dict[str, object] = Field(default_factory=dict)
    ground_truth: dict[str, object] | None = None
    confidence_score: float = Field(ge=0.0, le=1.0)
    calibration_status: CalibrationStatus = CalibrationStatus.PENDING
    drift_score: float | None = Field(default=None, ge=0.0)
    last_calibrated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    calibration_window: int = Field(ge=1, default=30)
    is_synthetic: bool = False
    tags: list[str] = Field(default_factory=list)
