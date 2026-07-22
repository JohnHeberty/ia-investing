from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from ia_investing.application.calibration_engine import CalibrationEngine
from ia_investing.domain.calibration import ComponentName


class CalibrationGateError(RuntimeError):
    def __init__(
        self,
        component: ComponentName | str,
        reason: str,
        detail: str = "",
    ) -> None:
        self.component = str(component)
        self.reason = reason
        super().__init__(f"Calibration gate blocked {component}: {reason}")


@dataclass(frozen=True, slots=True)
class GateOverride:
    id: UUID
    component: str
    reason: str
    requested_by: str
    created_at: datetime
    expires_at: datetime
    active: bool = True


class GateOverrideLog:
    def __init__(self) -> None:
        self._entries: list[GateOverride] = []

    def append(self, entry: GateOverride) -> None:
        self._entries.append(entry)

    def all(self) -> list[GateOverride]:
        return list(self._entries)

    def active_for(self, component: str) -> GateOverride | None:
        now = datetime.now(UTC)
        for entry in reversed(self._entries):
            if entry.component == component and entry.active and entry.expires_at > now:
                return entry
        return None


class ProductionGate:
    def __init__(
        self,
        engine: CalibrationEngine,
        override_log: GateOverrideLog | None = None,
    ) -> None:
        self._engine = engine
        self._override_log = override_log or GateOverrideLog()

    @property
    def override_log(self) -> GateOverrideLog:
        return self._override_log

    def require_calibration(
        self,
        component: ComponentName | str,
        min_records: int = 100,
        max_brier_score: float = 0.25,
    ) -> None:
        component_str = str(ComponentName(component))
        active = self._override_log.active_for(component_str)
        if active is not None:
            return

        score = self._engine.calculate_calibration_score(component)
        n_records = score.get("n_records", 0)
        brier = score.get("brier_score")

        if n_records < min_records:
            raise CalibrationGateError(
                component=component,
                reason="insufficient_records",
                detail=f"need {min_records}, have {n_records}",
            )
        if brier is None or brier > max_brier_score:
            raise CalibrationGateError(
                component=component,
                reason="brier_score_too_high",
                detail=f"max {max_brier_score}, got {brier}",
            )

    def get_gate_status(self) -> dict[str, Any]:
        summary = self._engine.get_calibration_summary()
        status: dict[str, Any] = {}
        for component_str, data in summary.items():
            component = ComponentName(component_str)
            active_override = self._override_log.active_for(str(component))
            gate_open = active_override is not None or (
                data["n_records"] is not None
                and (data["n_records"] or 0) >= 100
                and data["brier_score"] is not None
                and data["brier_score"] <= 0.25
            )
            status[str(component)] = {
                "gate_open": gate_open,
                "brier_score": data["brier_score"],
                "n_records": data["n_records"],
                "drift_detected": data["drift_detected"],
                "overridden": active_override is not None,
                "override_expires_at": active_override.expires_at.isoformat() if active_override else None,
            }
        return status

    def override_gate(
        self,
        component: ComponentName | str,
        reason: str,
        duration_hours: int = 24,
        requested_by: str = "system",
    ) -> GateOverride:
        component_str = str(ComponentName(component))
        now = datetime.now(UTC)
        override = GateOverride(
            id=uuid4(),
            component=component_str,
            reason=reason,
            requested_by=requested_by,
            created_at=now,
            expires_at=now + timedelta(hours=duration_hours),
        )
        self._override_log.append(override)
        return override
