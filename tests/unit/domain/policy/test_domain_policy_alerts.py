"""Unit tests for ia_investing.domain.policy_alerts — alert rules, firing, and deduplication."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from ia_investing.domain.policy_alerts import (
    DEFAULT_ALERT_RULES,
    AlertDeduplicationKey,
    AlertRule,
    AlertSeverity,
    AlertType,
    PolicyAlert,
    is_duplicate,
    should_fire_alert,
)

# ── Enums ─────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestAlertEnums:
    def test_alert_type_values(self) -> None:
        assert AlertType.STAGE_CHANGED == "stage_changed"
        assert AlertType.MATERIAL_IMPACT == "material_impact"
        assert AlertType.PROBABILITY_SHIFT == "probability_shift"
        assert AlertType.DEADLINE_APPROACHING == "deadline_approaching"
        assert AlertType.CORROBORATION_CONFLICT == "corroboration_conflict"
        assert AlertType.SOURCE_FRESHNESS == "source_freshness"

    def test_alert_severity_values(self) -> None:
        assert AlertSeverity.INFO == "info"
        assert AlertSeverity.WARNING == "warning"
        assert AlertSeverity.CRITICAL == "critical"

    def test_six_default_rules_defined(self) -> None:
        assert len(DEFAULT_ALERT_RULES) == 6
        types = {r.alert_type for r in DEFAULT_ALERT_RULES}
        assert types == set(AlertType)


# ── should_fire_alert ─────────────────────────────────────────────────────────


@pytest.mark.unit
class TestShouldFireAlert:
    def test_disabled_rule_never_fires(self) -> None:
        rule = AlertRule(
            alert_type=AlertType.STAGE_CHANGED,
            severity=AlertSeverity.INFO,
            threshold=Decimal("0"),
            description="test",
            enabled=False,
        )
        assert not should_fire_alert(rule, current_value=Decimal("999"))

    def test_stage_changed_always_fires(self) -> None:
        rule = DEFAULT_ALERT_RULES[0]  # STAGE_CHANGED
        assert should_fire_alert(rule, current_value=Decimal("0"))

    def test_material_impact_above_threshold(self) -> None:
        rule = DEFAULT_ALERT_RULES[1]  # MATERIAL_IMPACT threshold=0.20
        assert should_fire_alert(rule, current_value=Decimal("0.25"))

    def test_material_impact_below_threshold(self) -> None:
        rule = DEFAULT_ALERT_RULES[1]
        assert not should_fire_alert(rule, current_value=Decimal("0.10"))

    def test_material_impact_exact_threshold(self) -> None:
        rule = DEFAULT_ALERT_RULES[1]
        assert should_fire_alert(rule, current_value=Decimal("0.20"))

    def test_material_impact_zero_value(self) -> None:
        rule = DEFAULT_ALERT_RULES[1]
        assert not should_fire_alert(rule, current_value=Decimal("0"))

    def test_probability_shift_above_threshold(self) -> None:
        rule = DEFAULT_ALERT_RULES[2]  # PROBABILITY_SHIFT threshold=0.15
        assert should_fire_alert(rule, current_value=Decimal("0.50"), previous_value=Decimal("0.30"))

    def test_probability_shift_below_threshold(self) -> None:
        rule = DEFAULT_ALERT_RULES[2]
        assert not should_fire_alert(rule, current_value=Decimal("0.50"), previous_value=Decimal("0.45"))

    def test_probability_shift_no_previous_value(self) -> None:
        rule = DEFAULT_ALERT_RULES[2]
        assert should_fire_alert(rule, current_value=Decimal("0.50"), previous_value=None)

    def test_deadline_approaching_always_fires(self) -> None:
        rule = DEFAULT_ALERT_RULES[3]  # DEADLINE_APPROACHING
        assert should_fire_alert(rule, current_value=Decimal("0"))

    def test_corroboration_conflict_always_fires(self) -> None:
        rule = DEFAULT_ALERT_RULES[4]
        assert should_fire_alert(rule, current_value=Decimal("1"))

    def test_source_freshness_always_fires(self) -> None:
        rule = DEFAULT_ALERT_RULES[5]
        assert should_fire_alert(rule, current_value=Decimal("0"))


# ── is_duplicate ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestIsDuplicate:
    def test_first_call_never_duplicate(self) -> None:
        new = PolicyAlert(
            alert_type=AlertType.STAGE_CHANGED,
            policy_object_id=None,
            created_at=datetime.now(UTC),
        )
        assert not is_duplicate([], new)

    def test_duplicate_within_window(self) -> None:
        now = datetime.now(UTC)
        existing = PolicyAlert(
            alert_type=AlertType.STAGE_CHANGED,
            policy_object_id=None,
            created_at=now,
        )
        new = PolicyAlert(
            alert_type=AlertType.STAGE_CHANGED,
            policy_object_id=None,
            created_at=now + timedelta(minutes=30),
        )
        assert is_duplicate([existing], new, window_seconds=3600)

    def test_no_duplicate_after_window(self) -> None:
        now = datetime.now(UTC)
        existing = PolicyAlert(
            alert_type=AlertType.STAGE_CHANGED,
            policy_object_id=None,
            created_at=now - timedelta(hours=2),
        )
        new = PolicyAlert(
            alert_type=AlertType.STAGE_CHANGED,
            policy_object_id=None,
            created_at=now,
        )
        assert not is_duplicate([existing], new, window_seconds=3600)

    def test_different_type_not_duplicate(self) -> None:
        now = datetime.now(UTC)
        existing = PolicyAlert(
            alert_type=AlertType.STAGE_CHANGED,
            policy_object_id=None,
            created_at=now,
        )
        new = PolicyAlert(
            alert_type=AlertType.MATERIAL_IMPACT,
            policy_object_id=None,
            created_at=now,
        )
        assert not is_duplicate([existing], new)

    def test_resolved_alert_not_duplicate(self) -> None:
        now = datetime.now(UTC)
        existing = PolicyAlert(
            alert_type=AlertType.STAGE_CHANGED,
            policy_object_id=None,
            created_at=now,
            resolved=True,
        )
        new = PolicyAlert(
            alert_type=AlertType.STAGE_CHANGED,
            policy_object_id=None,
            created_at=now + timedelta(minutes=5),
        )
        assert not is_duplicate([existing], new)

    def test_different_object_id_not_duplicate(self) -> None:
        from uuid import uuid4

        now = datetime.now(UTC)
        oid1, oid2 = uuid4(), uuid4()
        existing = PolicyAlert(
            alert_type=AlertType.STAGE_CHANGED,
            policy_object_id=oid1,
            created_at=now,
        )
        new = PolicyAlert(
            alert_type=AlertType.STAGE_CHANGED,
            policy_object_id=oid2,
            created_at=now + timedelta(minutes=5),
        )
        assert not is_duplicate([existing], new)

    def test_deduplication_key_format(self) -> None:
        now = datetime.now(UTC)
        key = AlertDeduplicationKey(
            alert_type="stage_changed",
            resource_id="res-1",
            rule_id="rule-1",
            window_seconds=3600,
        )
        result = key.dedup_key(now)
        assert "stage_changed" in result
        assert "res-1" in result
        assert "rule-1" in result


# ── PolicyAlert defaults ──────────────────────────────────────────────────────


@pytest.mark.unit
class TestPolicyAlertDefaults:
    def test_default_fields(self) -> None:
        alert = PolicyAlert()
        assert alert.alert_type == AlertType.STAGE_CHANGED
        assert alert.severity == AlertSeverity.INFO
        assert alert.acknowledged is False
        assert alert.resolved is False
        assert alert.created_at is not None

    def test_custom_fields(self) -> None:
        now = datetime.now(UTC)
        alert = PolicyAlert(
            alert_type=AlertType.MATERIAL_IMPACT,
            severity=AlertSeverity.CRITICAL,
            title="Test",
            created_at=now,
        )
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.title == "Test"
