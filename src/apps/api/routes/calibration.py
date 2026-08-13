from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from apps.api._errors import map_error
from apps.api.security import AuthContext, require_permission
from ia_investing.application.calibration_engine import CalibrationEngine
from ia_investing.application.production_gate import ProductionGate
from ia_investing.domain.calibration import ComponentName

router = APIRouter(prefix="/api/v1/calibration", tags=["calibration"])
logger = structlog.get_logger("calibration")

_engine = CalibrationEngine()
_gate = ProductionGate(_engine)


def _get_engine() -> CalibrationEngine:
    return _engine


def _get_gate() -> ProductionGate:
    return _gate


class CalibrationStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    components: dict[str, Any]
    gate_status: dict[str, Any]
    uncalibrated: list[dict[str, Any]]


class ComponentStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    component: str
    calibration_score: dict[str, Any]
    drift: dict[str, Any]
    reliability: list[dict[str, Any]]
    gate: dict[str, Any]


class OverrideResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    component: str
    reason: str
    created_at: str
    expires_at: str
    requested_by: str


class OverrideActiveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    component: str
    reason: str
    requested_by: str
    created_at: str
    expires_at: str
    active: bool


@router.get("/status", response_model=CalibrationStatusResponse)
async def get_calibration_status(
    _auth: AuthContext = Depends(require_permission("calibration:read")),
    engine: CalibrationEngine = Depends(_get_engine),
    gate: ProductionGate = Depends(_get_gate),
) -> CalibrationStatusResponse:
    summary = engine.get_calibration_summary()
    gate_status = gate.get_gate_status()
    return CalibrationStatusResponse(
        components=summary,
        gate_status=gate_status,
        uncalibrated=engine.get_uncalibrated_components(),
    )


@router.get("/status/{component}", response_model=ComponentStatusResponse)
async def get_component_status(
    component: str,
    _auth: AuthContext = Depends(require_permission("calibration:read")),
    engine: CalibrationEngine = Depends(_get_engine),
    gate: ProductionGate = Depends(_get_gate),
) -> ComponentStatusResponse:
    try:
        comp = ComponentName(component)
    except ValueError as exc:
        raise map_error(LookupError(f"Unknown component: {component}")) from exc
    score = engine.calculate_calibration_score(comp)
    drift = engine.detect_drift(comp)
    reliability = engine.generate_reliability_data(comp)
    gate_status = gate.get_gate_status().get(str(comp), {})
    return ComponentStatusResponse(
        component=str(comp),
        calibration_score=score,
        drift=drift,
        reliability=reliability,
        gate=gate_status,
    )


@router.get("/reliability/{component}", response_model=list[dict[str, Any]])
async def get_reliability(
    component: str,
    _auth: AuthContext = Depends(require_permission("calibration:read")),
    engine: CalibrationEngine = Depends(_get_engine),
) -> list[dict[str, Any]]:
    try:
        comp = ComponentName(component)
    except ValueError as exc:
        raise map_error(LookupError(f"Unknown component: {component}")) from exc
    return engine.generate_reliability_data(comp)


class OverrideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=500)
    duration_hours: int = Field(default=24, ge=1, le=168)


@router.post("/override", response_model=OverrideResponse)
async def create_override(
    body: OverrideRequest,
    auth: AuthContext = Depends(require_permission("admin")),
    gate: ProductionGate = Depends(_get_gate),
) -> OverrideResponse:
    try:
        comp = ComponentName(body.component)
    except ValueError as exc:
        raise map_error(LookupError(f"Unknown component: {body.component}")) from exc
    override = gate.override_gate(comp, body.reason, body.duration_hours, requested_by=auth.subject)
    logger.info("calibration_override_created", component=body.component, reason=body.reason, requested_by=auth.subject)
    return OverrideResponse(
        id=str(override.id),
        component=override.component,
        reason=override.reason,
        created_at=override.created_at.isoformat(),
        expires_at=override.expires_at.isoformat(),
        requested_by=override.requested_by,
    )


@router.get("/overrides", response_model=list[OverrideActiveResponse])
async def list_overrides(
    auth: AuthContext = Depends(require_permission("admin")),
    gate: ProductionGate = Depends(_get_gate),
) -> list[OverrideActiveResponse]:
    return [
        OverrideActiveResponse(
            id=str(o.id),
            component=o.component,
            reason=o.reason,
            requested_by=o.requested_by,
            created_at=o.created_at.isoformat(),
            expires_at=o.expires_at.isoformat(),
            active=o.active,
        )
        for o in gate.override_log.all()
    ]
