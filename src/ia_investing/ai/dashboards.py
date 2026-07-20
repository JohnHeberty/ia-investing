from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from opentelemetry.metrics import get_meter

_MAX_BUFFER = 1_000


@dataclass(frozen=True, slots=True)
class MetricSnapshot:
    error_rate: float
    avg_cost_usd: float
    p95_latency_ms: float
    total_runs: int
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class DashboardConfig:
    max_error_rate: float = 0.1
    max_avg_cost_usd: float = 5.0
    max_p95_latency_ms: float = 30_000.0
    evaluation_window_seconds: float = 300.0


@dataclass(frozen=True, slots=True)
class AlertRule:
    name: str
    metric: Literal["error_rate", "avg_cost_usd", "p95_latency_ms"]
    threshold: float
    operator: Literal["gt", "lt", "gte", "lte"]
    severity: Literal["info", "warning", "critical"]


@dataclass(frozen=True, slots=True)
class AlertEvaluation:
    rule_name: str
    metric_value: float
    threshold: float
    violated: bool
    severity: Literal["info", "warning", "critical"]
    evaluated_at: datetime


class RuntimeDashboard:
    def __init__(self) -> None:
        self._meter = get_meter("ia_investing.dashboards")
        self._error_counter = self._meter.create_counter("agent.runtime.error_rate", unit="{error}")
        self._cost_histogram = self._meter.create_histogram("agent.runtime.cost_p95", unit="USD")
        self._latency_histogram = self._meter.create_histogram("agent.runtime.latency_p95", unit="ms")
        self._runs: deque[tuple[str, float, float]] = deque(maxlen=_MAX_BUFFER)

    def record_run(self, *, status: str, cost_usd: float, duration_ms: float) -> None:
        self._runs.append((status, cost_usd, duration_ms))
        attributes: dict[str, str] = {"agent.status": status}
        self._error_counter.add(0 if status == "success" else 1, attributes)
        self._cost_histogram.record(cost_usd, attributes)
        self._latency_histogram.record(duration_ms, attributes)

    def get_snapshot(self) -> MetricSnapshot:
        if not self._runs:
            return MetricSnapshot(
                error_rate=0.0,
                avg_cost_usd=0.0,
                p95_latency_ms=0.0,
                total_runs=0,
                timestamp=datetime.now(UTC),
            )
        total = len(self._runs)
        errors = sum(1 for status, _, _ in self._runs if status != "success")
        costs = sorted(cost_usd for _, cost_usd, _ in self._runs)
        latencies = sorted(duration_ms for _, _, duration_ms in self._runs)
        p95_index = max(0, int(len(latencies) * 0.95) - 1)
        return MetricSnapshot(
            error_rate=errors / total,
            avg_cost_usd=sum(costs) / total,
            p95_latency_ms=latencies[p95_index],
            total_runs=total,
            timestamp=datetime.now(UTC),
        )

    def evaluate_alerts(self, config: DashboardConfig) -> list[AlertEvaluation]:
        snapshot = self.get_snapshot()
        rules = [
            AlertRule(
                name="high_error_rate",
                metric="error_rate",
                threshold=config.max_error_rate,
                operator="gt",
                severity="critical",
            ),
            AlertRule(
                name="high_avg_cost",
                metric="avg_cost_usd",
                threshold=config.max_avg_cost_usd,
                operator="gt",
                severity="warning",
            ),
            AlertRule(
                name="high_p95_latency",
                metric="p95_latency_ms",
                threshold=config.max_p95_latency_ms,
                operator="gt",
                severity="warning",
            ),
        ]
        return [self._evaluate_rule(rule, snapshot) for rule in rules]

    def _evaluate_rule(self, rule: AlertRule, snapshot: MetricSnapshot) -> AlertEvaluation:
        metric_value = getattr(snapshot, rule.metric)
        violated = _compare(metric_value, rule.operator, rule.threshold)
        return AlertEvaluation(
            rule_name=rule.name,
            metric_value=metric_value,
            threshold=rule.threshold,
            violated=violated,
            severity=rule.severity,
            evaluated_at=snapshot.timestamp,
        )


def _compare(value: float, operator: str, threshold: float) -> bool:
    if operator == "gt":
        return value > threshold
    if operator == "lt":
        return value < threshold
    if operator == "gte":
        return value >= threshold
    if operator == "lte":
        return value <= threshold
    raise ValueError(f"unsupported operator: {operator}")
