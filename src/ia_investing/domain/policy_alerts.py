from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(StrEnum):
    STAGE_CHANGED = "stage_changed"
    MATERIAL_IMPACT = "material_impact"
    PROBABILITY_SHIFT = "probability_shift"
    DEADLINE_APPROACHING = "deadline_approaching"
    CORROBORATION_CONFLICT = "corroboration_conflict"
    SOURCE_FRESHNESS = "source_freshness"


@dataclass(frozen=True, slots=True)
class AlertRule:
    alert_type: AlertType
    severity: AlertSeverity
    threshold: Decimal
    description: str
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class AlertDeduplicationKey:
    alert_type: str
    resource_id: str
    rule_id: str
    window_seconds: int = 3600

    def dedup_key(self, now: datetime) -> str:
        window_start = now - timedelta(seconds=self.window_seconds)
        return f"{self.alert_type}:{self.resource_id}:{self.rule_id}:{window_start.isoformat()}"


@dataclass
class PolicyAlert:
    id: UUID = field(default_factory=uuid4)
    alert_type: AlertType = AlertType.STAGE_CHANGED
    severity: AlertSeverity = AlertSeverity.INFO
    policy_object_id: UUID | None = None
    title: str = ""
    description: str = ""
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    resolved: bool = False
    resolved_at: datetime | None = None


DEFAULT_ALERT_RULES: tuple[AlertRule, ...] = (
    AlertRule(
        alert_type=AlertType.STAGE_CHANGED,
        severity=AlertSeverity.WARNING,
        threshold=Decimal("0"),
        description="Político avançou de estágio jurídico",
    ),
    AlertRule(
        alert_type=AlertType.MATERIAL_IMPACT,
        severity=AlertSeverity.CRITICAL,
        threshold=Decimal("0.20"),
        description="Evento político com impacto material em carteira",
    ),
    AlertRule(
        alert_type=AlertType.PROBABILITY_SHIFT,
        severity=AlertSeverity.WARNING,
        threshold=Decimal("0.15"),
        description="Mudança significativa na probabilidade de aprovação",
    ),
    AlertRule(
        alert_type=AlertType.DEADLINE_APPROACHING,
        severity=AlertSeverity.INFO,
        threshold=Decimal("0"),
        description="Prazo legislativo se aproxima",
    ),
    AlertRule(
        alert_type=AlertType.CORROBORATION_CONFLICT,
        severity=AlertSeverity.CRITICAL,
        threshold=Decimal("0"),
        description="Evidências conflitantes sobre evento político",
    ),
    AlertRule(
        alert_type=AlertType.SOURCE_FRESHNESS,
        severity=AlertSeverity.WARNING,
        threshold=Decimal("0"),
        description="Fonte de dados político com freshness abaixo do SLA",
    ),
)


def should_fire_alert(
    rule: AlertRule,
    *,
    current_value: Decimal,
    previous_value: Decimal | None = None,
) -> bool:
    if not rule.enabled:
        return False
    if rule.alert_type == AlertType.PROBABILITY_SHIFT and previous_value is not None:
        shift = abs(current_value - previous_value)
        return shift >= rule.threshold
    if rule.alert_type == AlertType.MATERIAL_IMPACT:
        return current_value >= rule.threshold
    return True


def is_duplicate(
    existing_alerts: list[PolicyAlert],
    new_alert: PolicyAlert,
    *,
    window_seconds: int = 3600,
) -> bool:
    cutoff = new_alert.created_at - timedelta(seconds=window_seconds)
    for alert in existing_alerts:
        if (
            alert.alert_type == new_alert.alert_type
            and alert.policy_object_id == new_alert.policy_object_id
            and alert.created_at >= cutoff
            and not alert.resolved
        ):
            return True
    return False
