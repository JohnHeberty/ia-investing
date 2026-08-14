"""Unit tests for ia_investing.application.alert_evaluator."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from database.models.policy_intelligence import (
    PolicyObject,
    PolicyStageEvent,
)
from ia_investing.application.alert_evaluator import (
    AlertEvaluator,
    _extract_current_value,
    _extract_previous_value,
    _generate_description,
)
from ia_investing.domain.policy_alerts import (
    AlertRule,
    AlertSeverity,
    AlertType,
)


@pytest.fixture()
def session() -> AsyncMock:
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.flush = AsyncMock()
    mock.execute = AsyncMock()
    mock.add = MagicMock()
    return mock


@pytest.fixture()
def policy_object_id() -> UUID:
    return uuid4()


_now = datetime.now(UTC)


def _make_policy_obj(title: str = "PL 123/2026") -> MagicMock:
    obj = MagicMock(spec=PolicyObject)
    obj.id = uuid4()
    obj.title = title
    obj.authority = "Senado"
    return obj


def _make_version(metadata: dict | None = None) -> MagicMock:
    v = MagicMock()
    v.id = uuid4()
    v.version = 3
    v.text_content = "text"
    v.metadata_payload = metadata or {}
    v.published_at = _now
    v.knowledge_at = _now
    return v


def _make_stage_event(stage: str = "comissao") -> MagicMock:
    e = MagicMock(spec=PolicyStageEvent)
    e.id = uuid4()
    e.stage = stage
    e.occurred_at = _now
    e.knowledge_at = _now
    e.metadata_payload = {}
    return e


def _make_db_alert(
    *,
    policy_object_id: UUID | None = None,
    alert_type: str = "stage_changed",
    severity: str = "warning",
    fired_at: datetime | None = None,
    resolved_at: datetime | None = None,
) -> MagicMock:
    a = MagicMock()
    a.id = uuid4()
    a.alert_type = alert_type
    a.severity = severity
    a.policy_object_id = policy_object_id or uuid4()
    a.title = f"{alert_type}: test"
    a.description = "desc"
    a.details = {}
    a.fired_at = fired_at or _now
    a.resolved_at = resolved_at
    a.acknowledged_at = None
    return a


def _make_scalars_result(items: list) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.__iter__ = MagicMock(return_value=iter(items))
    result.scalars.return_value.all.return_value = items
    return result


def _make_scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _mock_execute_sequence(session: AsyncMock, results: list[MagicMock]) -> None:
    """Configure session.execute to return results in order via side_effect."""
    call_idx = 0

    async def _next(stmt: object) -> MagicMock:
        nonlocal call_idx
        r = results[call_idx]
        call_idx += 1
        return r

    session.execute = AsyncMock(side_effect=_next)


# ── _extract_current_value ────────────────────────────────────────────────


@pytest.mark.unit
class TestExtractCurrentValue:
    def test_probability_shift_with_forecasts(self) -> None:
        rule = AlertRule(
            alert_type=AlertType.PROBABILITY_SHIFT,
            severity=AlertSeverity.WARNING,
            threshold=Decimal("0.15"),
            description="test",
        )
        ctx = {"forecasts": [{"probability": 0.75}, {"probability": 0.50}]}
        assert _extract_current_value(rule, ctx) == Decimal("0.75")

    def test_probability_shift_no_forecasts(self) -> None:
        rule = AlertRule(
            alert_type=AlertType.PROBABILITY_SHIFT,
            severity=AlertSeverity.WARNING,
            threshold=Decimal("0.15"),
            description="test",
        )
        assert _extract_current_value(rule, {}) == Decimal("0")

    def test_material_impact_with_metadata(self) -> None:
        rule = AlertRule(
            alert_type=AlertType.MATERIAL_IMPACT,
            severity=AlertSeverity.CRITICAL,
            threshold=Decimal("0.20"),
            description="test",
        )
        ctx = {"version_metadata": {"material_impact_score": 0.35}}
        assert _extract_current_value(rule, ctx) == Decimal("0.35")

    def test_material_impact_no_metadata(self) -> None:
        rule = AlertRule(
            alert_type=AlertType.MATERIAL_IMPACT,
            severity=AlertSeverity.CRITICAL,
            threshold=Decimal("0.20"),
            description="test",
        )
        assert _extract_current_value(rule, {}) == Decimal("0")

    def test_deadline_approaching(self) -> None:
        rule = AlertRule(
            alert_type=AlertType.DEADLINE_APPROACHING,
            severity=AlertSeverity.INFO,
            threshold=Decimal("0"),
            description="test",
        )
        ctx = {"deadline_days": 5}
        assert _extract_current_value(rule, ctx) == Decimal("5")

    def test_deadline_approaching_no_deadline(self) -> None:
        rule = AlertRule(
            alert_type=AlertType.DEADLINE_APPROACHING,
            severity=AlertSeverity.INFO,
            threshold=Decimal("0"),
            description="test",
        )
        assert _extract_current_value(rule, {}) == Decimal("999")

    def test_source_freshness(self) -> None:
        rule = AlertRule(
            alert_type=AlertType.SOURCE_FRESHNESS,
            severity=AlertSeverity.WARNING,
            threshold=Decimal("0"),
            description="test",
        )
        ctx = {"source_freshness_hours": 48}
        assert _extract_current_value(rule, ctx) == Decimal("48")

    def test_unknown_type_returns_zero(self) -> None:
        rule = AlertRule(
            alert_type=AlertType.STAGE_CHANGED,
            severity=AlertSeverity.WARNING,
            threshold=Decimal("0"),
            description="test",
        )
        assert _extract_current_value(rule, {}) == Decimal("0")


# ── _extract_previous_value ───────────────────────────────────────────────


@pytest.mark.unit
class TestExtractPreviousValue:
    def test_probability_shift_two_forecasts(self) -> None:
        rule = AlertRule(
            alert_type=AlertType.PROBABILITY_SHIFT,
            severity=AlertSeverity.WARNING,
            threshold=Decimal("0.15"),
            description="test",
        )
        ctx = {"forecasts": [{"probability": 0.75}, {"probability": 0.50}]}
        assert _extract_previous_value(rule, ctx) == Decimal("0.50")

    def test_probability_shift_one_forecast(self) -> None:
        rule = AlertRule(
            alert_type=AlertType.PROBABILITY_SHIFT,
            severity=AlertSeverity.WARNING,
            threshold=Decimal("0.15"),
            description="test",
        )
        ctx = {"forecasts": [{"probability": 0.75}]}
        assert _extract_previous_value(rule, ctx) is None

    def test_non_probability_type_returns_none(self) -> None:
        rule = AlertRule(
            alert_type=AlertType.MATERIAL_IMPACT,
            severity=AlertSeverity.CRITICAL,
            threshold=Decimal("0.20"),
            description="test",
        )
        assert _extract_previous_value(rule, {}) is None


# ── _generate_description ─────────────────────────────────────────────────


@pytest.mark.unit
class TestGenerateDescription:
    def test_with_policy_object(self) -> None:
        rule = AlertRule(
            alert_type=AlertType.STAGE_CHANGED,
            severity=AlertSeverity.WARNING,
            threshold=Decimal("0"),
            description="Político avançou",
        )
        obj = _make_policy_obj("PL 456/2026")
        result = _generate_description(rule, {"policy_object": obj})
        assert result == "Político avançou — PL 456/2026"

    def test_without_policy_object(self) -> None:
        rule = AlertRule(
            alert_type=AlertType.STAGE_CHANGED,
            severity=AlertSeverity.WARNING,
            threshold=Decimal("0"),
            description="Alerta",
        )
        result = _generate_description(rule, {})
        assert result == "Alerta — unknown"


# ── AlertEvaluator.evaluate_policy_object ─────────────────────────────────


@pytest.mark.unit
class TestEvaluatePolicyObject:
    async def test_returns_empty_when_policy_not_found(self, session: AsyncMock, policy_object_id: UUID) -> None:
        session.get.return_value = None

        evaluator = AlertEvaluator(session)
        result = await evaluator.evaluate_policy_object(policy_object_id=policy_object_id)
        assert result == []

    async def test_returns_empty_when_no_version(self, session: AsyncMock, policy_object_id: UUID) -> None:
        session.get.return_value = _make_policy_obj()
        _mock_execute_sequence(
            session,
            [
                _make_scalar_result(None),
            ],
        )

        evaluator = AlertEvaluator(session)
        result = await evaluator.evaluate_policy_object(policy_object_id=policy_object_id)
        assert result == []

    async def test_fires_stage_changed_alert(self, session: AsyncMock, policy_object_id: UUID) -> None:
        policy_obj = _make_policy_obj("PL 100/2026")
        version = _make_version()
        stage_event = _make_stage_event()

        session.get.return_value = policy_obj
        _mock_execute_sequence(
            session,
            [
                _make_scalar_result(version),
                _make_scalars_result([stage_event]),
                _make_scalars_result([]),
            ],
        )

        evaluator = AlertEvaluator(session)
        result = await evaluator.evaluate_policy_object(policy_object_id=policy_object_id)

        assert len(result) >= 1
        stage_alerts = [a for a in result if a.alert_type == "stage_changed"]
        assert len(stage_alerts) == 1
        assert stage_alerts[0].severity == "warning"
        assert stage_alerts[0].policy_object_id == policy_object_id
        assert "PL 100/2026" in stage_alerts[0].title
        session.add.assert_called()
        session.flush.assert_awaited()

    async def test_material_impact_below_threshold_no_alert(self, session: AsyncMock, policy_object_id: UUID) -> None:
        policy_obj = _make_policy_obj()
        version = _make_version(metadata={"material_impact_score": 0.05})

        session.get.return_value = policy_obj
        _mock_execute_sequence(
            session,
            [
                _make_scalar_result(version),
                _make_scalars_result([]),
                _make_scalars_result([]),
            ],
        )

        evaluator = AlertEvaluator(session)
        result = await evaluator.evaluate_policy_object(policy_object_id=policy_object_id)

        impact_alerts = [a for a in result if a.alert_type == "material_impact"]
        assert len(impact_alerts) == 0

    async def test_skips_duplicate_alerts(self, session: AsyncMock, policy_object_id: UUID) -> None:
        policy_obj = _make_policy_obj("PL 200/2026")
        version = _make_version()
        existing = _make_db_alert(
            policy_object_id=policy_object_id,
            alert_type="stage_changed",
            fired_at=_now,
        )

        session.get.return_value = policy_obj
        _mock_execute_sequence(
            session,
            [
                _make_scalar_result(version),
                _make_scalars_result([]),
                _make_scalars_result([existing]),
            ],
        )

        evaluator = AlertEvaluator(session)
        result = await evaluator.evaluate_policy_object(policy_object_id=policy_object_id)

        stage_alerts = [a for a in result if a.alert_type == "stage_changed"]
        assert len(stage_alerts) == 0


# ── AlertEvaluator.evaluate_all_policies ──────────────────────────────────


@pytest.mark.unit
class TestEvaluateAllPolicies:
    async def test_empty_policy_list(self, session: AsyncMock) -> None:
        _mock_execute_sequence(
            session,
            [
                _make_scalars_result([]),
            ],
        )

        evaluator = AlertEvaluator(session)
        result = await evaluator.evaluate_all_policies()
        assert result == []

    async def test_multiple_policies_returns_empty(self, session: AsyncMock) -> None:
        pid1, pid2 = uuid4(), uuid4()

        session.get.return_value = None
        _mock_execute_sequence(
            session,
            [
                _make_scalars_result([pid1, pid2]),
            ],
        )

        evaluator = AlertEvaluator(session)
        result = await evaluator.evaluate_all_policies()
        assert result == []
