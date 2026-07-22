from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from apps.api.security import AuthContext, require_permission
from ia_investing.application.calibration_engine import CalibrationEngine
from ia_investing.application.production_gate import ProductionGate
from ia_investing.domain.calibration import ComponentName

router = APIRouter(prefix="/api/v1/calibration", tags=["calibration"])

_engine = CalibrationEngine()
_gate = ProductionGate(_engine)


def _get_engine() -> CalibrationEngine:
    return _engine


def _get_gate() -> ProductionGate:
    return _gate


@router.get("/status")
async def get_calibration_status(
    engine: CalibrationEngine = Depends(_get_engine),
    gate: ProductionGate = Depends(_get_gate),
) -> dict[str, Any]:
    summary = engine.get_calibration_summary()
    gate_status = gate.get_gate_status()
    return {
        "components": summary,
        "gate_status": gate_status,
        "uncalibrated": engine.get_uncalibrated_components(),
    }


@router.get("/status/{component}")
async def get_component_status(
    component: str,
    engine: CalibrationEngine = Depends(_get_engine),
    gate: ProductionGate = Depends(_get_gate),
) -> dict[str, Any]:
    try:
        comp = ComponentName(component)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown component: {component}") from None
    score = engine.calculate_calibration_score(comp)
    drift = engine.detect_drift(comp)
    reliability = engine.generate_reliability_data(comp)
    gate_status = gate.get_gate_status().get(str(comp), {})
    return {
        "component": str(comp),
        "calibration_score": score,
        "drift": drift,
        "reliability": reliability,
        "gate": gate_status,
    }


@router.get("/reliability/{component}")
async def get_reliability(
    component: str,
    engine: CalibrationEngine = Depends(_get_engine),
) -> list[dict[str, Any]]:
    try:
        comp = ComponentName(component)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown component: {component}") from None
    return engine.generate_reliability_data(comp)


class OverrideRequest:
    def __init__(self, component: str, reason: str, duration_hours: int = 24) -> None:
        self.component = component
        self.reason = reason
        self.duration_hours = duration_hours


@router.post("/override")
async def create_override(
    body: OverrideRequest,
    auth: AuthContext = Depends(require_permission("admin")),
    gate: ProductionGate = Depends(_get_gate),
) -> dict[str, Any]:
    try:
        comp = ComponentName(body.component)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown component: {body.component}") from None
    override = gate.override_gate(comp, body.reason, body.duration_hours, requested_by=auth.subject)
    return {
        "id": str(override.id),
        "component": override.component,
        "reason": override.reason,
        "created_at": override.created_at.isoformat(),
        "expires_at": override.expires_at.isoformat(),
        "requested_by": override.requested_by,
    }


@router.get("/overrides")
async def list_overrides(
    auth: AuthContext = Depends(require_permission("admin")),
    gate: ProductionGate = Depends(_get_gate),
) -> list[dict[str, Any]]:
    return [
        {
            "id": str(o.id),
            "component": o.component,
            "reason": o.reason,
            "requested_by": o.requested_by,
            "created_at": o.created_at.isoformat(),
            "expires_at": o.expires_at.isoformat(),
            "active": o.active,
        }
        for o in gate.override_log.all()
    ]
