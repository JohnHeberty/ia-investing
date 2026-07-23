from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


def _get(line_items: dict[str, Any], key: str) -> float:
    raw = line_items.get(key)
    if raw is None:
        raise ValueError(f"required financial field is missing: {key}")
    return float(raw)


@dataclass(slots=True)
class ValidationResult:
    check_name: str
    passed: bool
    entity_type: str
    entity_id: str
    details: dict[str, Any] = field(default_factory=dict)
    severity: Literal["error", "warning", "info"] = "warning"


def _make(
    check: str,
    passed: bool,
    entity_type: str,
    entity_id: str,
    severity: Literal["error", "warning", "info"] = "warning",
    **details: object,
) -> ValidationResult:
    return ValidationResult(
        check_name=check,
        passed=passed,
        entity_type=entity_type,
        entity_id=entity_id,
        details=dict(details),
        severity=severity,
    )


def _close(a: float, b: float, tolerance_pct: float = 0.001) -> bool:
    if a == 0 and b == 0:
        return True
    denom = max(abs(a), abs(b), 1.0)
    return abs(a - b) / denom <= tolerance_pct
