from __future__ import annotations

import pytest

from ia_investing.ai.dashboards import (
    AlertEvaluation,
    AlertRule,
    DashboardConfig,
    RuntimeDashboard,
    _compare,
)


def test_record_run_updates_snapshot_correctly() -> None:
    dashboard = RuntimeDashboard()
    dashboard.record_run(status="success", cost_usd=1.5, duration_ms=200.0)
    dashboard.record_run(status="success", cost_usd=2.5, duration_ms=300.0)
    snapshot = dashboard.get_snapshot()
    assert snapshot.total_runs == 2
    assert snapshot.error_rate == 0.0
    assert snapshot.avg_cost_usd == pytest.approx(2.0)
    assert snapshot.p95_latency_ms == pytest.approx(200.0)


def test_record_run_with_errors_updates_error_rate() -> None:
    dashboard = RuntimeDashboard()
    dashboard.record_run(status="success", cost_usd=1.0, duration_ms=100.0)
    dashboard.record_run(status="failed", cost_usd=2.0, duration_ms=150.0)
    dashboard.record_run(status="failed", cost_usd=3.0, duration_ms=200.0)
    snapshot = dashboard.get_snapshot()
    assert snapshot.total_runs == 3
    assert snapshot.error_rate == pytest.approx(2.0 / 3.0)


def test_empty_state_returns_zero_metrics() -> None:
    dashboard = RuntimeDashboard()
    snapshot = dashboard.get_snapshot()
    assert snapshot.error_rate == 0.0
    assert snapshot.avg_cost_usd == 0.0
    assert snapshot.p95_latency_ms == 0.0
    assert snapshot.total_runs == 0


def test_rolling_window_limits_to_1000_entries() -> None:
    dashboard = RuntimeDashboard()
    for _i in range(1_200):
        dashboard.record_run(status="success", cost_usd=1.0, duration_ms=100.0)
    snapshot = dashboard.get_snapshot()
    assert snapshot.total_runs == 1_000
    assert len(dashboard._runs) == 1_000


def test_alert_evaluation_violated_rules() -> None:
    dashboard = RuntimeDashboard()
    for _ in range(10):
        dashboard.record_run(status="failed", cost_usd=10.0, duration_ms=50_000.0)
    config = DashboardConfig(
        max_error_rate=0.1,
        max_avg_cost_usd=5.0,
        max_p95_latency_ms=30_000.0,
    )
    evaluations = dashboard.evaluate_alerts(config)
    assert len(evaluations) == 3
    assert all(ev.violated for ev in evaluations)
    assert evaluations[0].rule_name == "high_error_rate"
    assert evaluations[0].severity == "critical"
    assert evaluations[1].rule_name == "high_avg_cost"
    assert evaluations[1].severity == "warning"
    assert evaluations[2].rule_name == "high_p95_latency"
    assert evaluations[2].severity == "warning"


def test_alert_evaluation_non_violated_rules() -> None:
    dashboard = RuntimeDashboard()
    for _ in range(10):
        dashboard.record_run(status="success", cost_usd=1.0, duration_ms=100.0)
    config = DashboardConfig(
        max_error_rate=0.5,
        max_avg_cost_usd=5.0,
        max_p95_latency_ms=30_000.0,
    )
    evaluations = dashboard.evaluate_alerts(config)
    assert len(evaluations) == 3
    assert not any(ev.violated for ev in evaluations)


def test_multiple_alert_severities() -> None:
    dashboard = RuntimeDashboard()
    for _ in range(5):
        dashboard.record_run(status="success", cost_usd=1.0, duration_ms=100.0)
    config = DashboardConfig()
    evaluations = dashboard.evaluate_alerts(config)
    severities = {ev.severity for ev in evaluations}
    assert severities == {"warning", "critical"}


def test_all_operators_gt() -> None:
    assert _compare(5.0, "gt", 3.0) is True
    assert _compare(3.0, "gt", 3.0) is False
    assert _compare(1.0, "gt", 3.0) is False


def test_all_operators_lt() -> None:
    assert _compare(1.0, "lt", 3.0) is True
    assert _compare(3.0, "lt", 3.0) is False
    assert _compare(5.0, "lt", 3.0) is False


def test_all_operators_gte() -> None:
    assert _compare(5.0, "gte", 3.0) is True
    assert _compare(3.0, "gte", 3.0) is True
    assert _compare(1.0, "gte", 3.0) is False


def test_all_operators_lte() -> None:
    assert _compare(1.0, "lte", 3.0) is True
    assert _compare(3.0, "lte", 3.0) is True
    assert _compare(5.0, "lte", 3.0) is False


def test_all_operators_invalid_raises() -> None:
    with pytest.raises(ValueError, match="unsupported operator"):
        _compare(1.0, "ne", 3.0)


def test_p95_latency_calculation() -> None:
    dashboard = RuntimeDashboard()
    for i in range(100):
        dashboard.record_run(status="success", cost_usd=1.0, duration_ms=float(i + 1))
    snapshot = dashboard.get_snapshot()
    assert snapshot.total_runs == 100
    assert snapshot.p95_latency_ms == pytest.approx(95.0)


def test_snapshot_timestamp_is_set() -> None:
    dashboard = RuntimeDashboard()
    dashboard.record_run(status="success", cost_usd=1.0, duration_ms=100.0)
    snapshot = dashboard.get_snapshot()
    assert snapshot.timestamp is not None
    assert snapshot.timestamp.year >= 2024


def test_evaluate_alerts_returns_evaluated_at() -> None:
    dashboard = RuntimeDashboard()
    dashboard.record_run(status="success", cost_usd=1.0, duration_ms=100.0)
    evaluations = dashboard.evaluate_alerts(DashboardConfig())
    for ev in evaluations:
        assert ev.evaluated_at is not None
        assert isinstance(ev, AlertEvaluation)


def test_config_defaults() -> None:
    config = DashboardConfig()
    assert config.max_error_rate == 0.1
    assert config.max_avg_cost_usd == 5.0
    assert config.max_p95_latency_ms == 30_000.0
    assert config.evaluation_window_seconds == 300.0


def test_alert_rule_frozen() -> None:
    rule = AlertRule(
        name="test",
        metric="error_rate",
        threshold=0.1,
        operator="gt",
        severity="warning",
    )
    with pytest.raises(AttributeError):
        rule.name = "changed"  # type: ignore[misc]
