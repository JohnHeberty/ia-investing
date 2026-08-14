"""Unit tests for ia_investing.application.policy_intelligence — application services."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from database.models.policy_intelligence import (
    PolicyAlert,
    PolicyObject,
    PolicyProbabilityForecast,
    RegulatoryAction,
)
from ia_investing.application.policy_intelligence import (
    PolicyAlertService,
    ProbabilityForecastService,
    RegulatoryActionService,
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


@pytest.fixture()
def source_object_version_id() -> UUID:
    return uuid4()


_now = datetime.now(UTC)


# ── RegulatoryActionService ───────────────────────────────────────────────


@pytest.mark.unit
class TestRegulatoryActionServiceIngest:
    async def test_happy_path(self, session: AsyncMock, policy_object_id: UUID, source_object_version_id: UUID) -> None:
        policy_obj = MagicMock(spec=PolicyObject)
        session.get.return_value = policy_obj

        svc = RegulatoryActionService(session)
        result = await svc.ingest(
            policy_object_id=policy_object_id,
            action_type="normative",
            title="CMN Resolution 123",
            issued_at=_now,
            rectifies=False,
            authority="CMN",
            external_id="CMN-2026-001",
            source_object_version_id=source_object_version_id,
            content_sha256="a" * 64,
            metadata_payload={"key": "value"},
            knowledge_at=_now,
            actor_subject="analyst@example.com",
            permissions=frozenset({"policy:write"}),
        )

        assert isinstance(result, RegulatoryAction)
        assert result.policy_object_id == policy_object_id
        assert result.action_type == "normative"
        assert result.external_id == "CMN-2026-001"
        assert result.rectifies is False
        session.add.assert_called_once()
        session.flush.assert_awaited_once()

    async def test_permission_denied(self, session: AsyncMock, policy_object_id: UUID, source_object_version_id: UUID) -> None:
        svc = RegulatoryActionService(session)
        with pytest.raises(PermissionError, match="policy:write"):
            await svc.ingest(
                policy_object_id=policy_object_id,
                action_type="normative",
                title="Test",
                issued_at=_now,
                authority="CMN",
                external_id="EXT-001",
                source_object_version_id=source_object_version_id,
                content_sha256="a" * 64,
                metadata_payload={},
                knowledge_at=_now,
                actor_subject="user@example.com",
                permissions=frozenset(),
            )

    async def test_permission_data_write_accepted(self, session: AsyncMock, policy_object_id: UUID, source_object_version_id: UUID) -> None:
        session.get.return_value = MagicMock(spec=PolicyObject)

        svc = RegulatoryActionService(session)
        result = await svc.ingest(
            policy_object_id=policy_object_id,
            action_type="circular",
            title="BCB Circular 4000",
            issued_at=_now,
            authority="BCB",
            external_id="BCB-2026-002",
            source_object_version_id=source_object_version_id,
            content_sha256="b" * 64,
            metadata_payload={},
            knowledge_at=_now,
            actor_subject="user",
            permissions=frozenset({"data:write"}),
        )
        assert isinstance(result, RegulatoryAction)

    async def test_policy_object_not_found(self, session: AsyncMock, policy_object_id: UUID, source_object_version_id: UUID) -> None:
        session.get.return_value = None

        svc = RegulatoryActionService(session)
        with pytest.raises(LookupError, match="policy object not found"):
            await svc.ingest(
                policy_object_id=policy_object_id,
                action_type="normative",
                title="Test",
                issued_at=_now,
                authority="CMN",
                external_id="EXT-001",
                source_object_version_id=source_object_version_id,
                content_sha256="a" * 64,
                metadata_payload={},
                knowledge_at=_now,
                actor_subject="user",
                permissions=frozenset({"policy:write"}),
            )


# ── ProbabilityForecastService ────────────────────────────────────────────


@pytest.mark.unit
class TestProbabilityForecastServiceCreateForecast:
    async def test_happy_path(self, session: AsyncMock, policy_object_id: UUID) -> None:
        svc = ProbabilityForecastService(session)
        result = await svc.create_forecast(
            policy_object_id=policy_object_id,
            target_outcome="approval",
            probability=Decimal("0.75"),
            interval_low=Decimal("0.60"),
            interval_high=Decimal("0.85"),
            factors={"stance": "favorable"},
            methodology_version="v1.0",
            features_sha256="c" * 64,
            assumptions=["historical base rate"],
            predicted_at=_now,
            knowledge_cutoff=_now,
        )

        assert isinstance(result, PolicyProbabilityForecast)
        assert result.probability == Decimal("0.75")
        assert result.target_outcome == "approval"
        assert result.methodology_version == "v1.0"
        session.add.assert_called_once()
        session.flush.assert_awaited_once()

    async def test_probability_out_of_range_zero(self, session: AsyncMock, policy_object_id: UUID) -> None:
        svc = ProbabilityForecastService(session)
        with pytest.raises(ValueError, match="probability must be between 0 and 1"):
            await svc.create_forecast(
                policy_object_id=policy_object_id,
                target_outcome="approval",
                probability=Decimal("1.5"),
                methodology_version="v1.0",
                features_sha256="c" * 64,
                predicted_at=_now,
                knowledge_cutoff=_now,
            )

    async def test_probability_out_of_range_negative(self, session: AsyncMock, policy_object_id: UUID) -> None:
        svc = ProbabilityForecastService(session)
        with pytest.raises(ValueError, match="probability must be between 0 and 1"):
            await svc.create_forecast(
                policy_object_id=policy_object_id,
                target_outcome="approval",
                probability=Decimal("-0.1"),
                methodology_version="v1.0",
                features_sha256="c" * 64,
                predicted_at=_now,
                knowledge_cutoff=_now,
            )

    async def test_invalid_interval(self, session: AsyncMock, policy_object_id: UUID) -> None:
        svc = ProbabilityForecastService(session)
        with pytest.raises(ValueError, match="interval must satisfy"):
            await svc.create_forecast(
                policy_object_id=policy_object_id,
                target_outcome="approval",
                probability=Decimal("0.5"),
                interval_low=Decimal("0.8"),
                interval_high=Decimal("0.9"),
                methodology_version="v1.0",
                features_sha256="c" * 64,
                predicted_at=_now,
                knowledge_cutoff=_now,
            )

    async def test_default_intervals(self, session: AsyncMock, policy_object_id: UUID) -> None:
        svc = ProbabilityForecastService(session)
        result = await svc.create_forecast(
            policy_object_id=policy_object_id,
            target_outcome="veto",
            probability=Decimal("0.30"),
            methodology_version="v2.0",
            features_sha256="d" * 64,
            predicted_at=_now,
            knowledge_cutoff=_now,
        )
        assert result.interval_low == Decimal("0.30")
        assert result.interval_high == Decimal("0.30")

    async def test_list_forecasts(self, session: AsyncMock, policy_object_id: UUID) -> None:
        mock_row = MagicMock(spec=PolicyProbabilityForecast)
        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value.__iter__ = MagicMock(return_value=iter([mock_row]))
        session.execute.return_value = mock_scalars

        svc = ProbabilityForecastService(session)
        result = await svc.list_forecasts(policy_object_id=policy_object_id)
        assert result == [mock_row]
        session.execute.assert_awaited_once()


# ── PolicyAlertService ────────────────────────────────────────────────────


def _make_alert(
    *,
    alert_id: UUID | None = None,
    policy_object_id: UUID | None = None,
    fired_at: datetime = _now,
    acknowledged_at: datetime | None = None,
    resolved_at: datetime | None = None,
) -> MagicMock:
    alert = MagicMock(spec=PolicyAlert)
    alert.id = alert_id or uuid4()
    alert.policy_object_id = policy_object_id or uuid4()
    alert.fired_at = fired_at
    alert.acknowledged_at = acknowledged_at
    alert.acknowledged_by = None
    alert.resolved_at = resolved_at
    alert.resolved_by = None
    alert.resolution_notes = None
    return alert


@pytest.mark.unit
class TestPolicyAlertServiceListAlerts:
    async def test_list_all_active(self, session: AsyncMock) -> None:
        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_scalars

        svc = PolicyAlertService(session)
        result = await svc.list_alerts(status="active")
        assert result == []

    async def test_list_by_policy_object(self, session: AsyncMock, policy_object_id: UUID) -> None:
        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_scalars

        svc = PolicyAlertService(session)
        result = await svc.list_alerts(policy_object_id=policy_object_id)
        assert result == []

    async def test_list_acknowledged(self, session: AsyncMock) -> None:
        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_scalars

        svc = PolicyAlertService(session)
        result = await svc.list_alerts(status="acknowledged")
        assert result == []

    async def test_list_resolved(self, session: AsyncMock) -> None:
        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_scalars

        svc = PolicyAlertService(session)
        result = await svc.list_alerts(status="resolved")
        assert result == []


@pytest.mark.unit
class TestPolicyAlertServiceAcknowledge:
    async def test_happy_path(self, session: AsyncMock) -> None:
        alert = _make_alert()
        session.get.return_value = alert

        svc = PolicyAlertService(session)
        result = await svc.acknowledge(alert_id=alert.id, actor="analyst@example.com")

        assert result.acknowledged_by == "analyst@example.com"
        assert result.acknowledged_at is not None
        session.flush.assert_awaited_once()

    async def test_already_acknowledged(self, session: AsyncMock) -> None:
        alert = _make_alert(acknowledged_at=_now)
        session.get.return_value = alert

        svc = PolicyAlertService(session)
        with pytest.raises(ValueError, match="alert already acknowledged"):
            await svc.acknowledge(alert_id=alert.id, actor="user")

    async def test_not_found(self, session: AsyncMock) -> None:
        session.get.return_value = None

        svc = PolicyAlertService(session)
        with pytest.raises(LookupError, match="alert not found"):
            await svc.acknowledge(alert_id=uuid4(), actor="user")


@pytest.mark.unit
class TestPolicyAlertServiceResolve:
    async def test_happy_path(self, session: AsyncMock) -> None:
        alert = _make_alert()
        session.get.return_value = alert

        svc = PolicyAlertService(session)
        result = await svc.resolve(
            alert_id=alert.id,
            actor="supervisor@example.com",
            notes="Policy updated, no longer relevant",
        )

        assert result.resolved_by == "supervisor@example.com"
        assert result.resolution_notes == "Policy updated, no longer relevant"
        assert result.resolved_at is not None
        session.flush.assert_awaited_once()

    async def test_already_resolved(self, session: AsyncMock) -> None:
        alert = _make_alert(resolved_at=_now)
        session.get.return_value = alert

        svc = PolicyAlertService(session)
        with pytest.raises(ValueError, match="alert already resolved"):
            await svc.resolve(alert_id=alert.id, actor="user", notes="n/a")

    async def test_not_found(self, session: AsyncMock) -> None:
        session.get.return_value = None

        svc = PolicyAlertService(session)
        with pytest.raises(LookupError, match="alert not found"):
            await svc.resolve(alert_id=uuid4(), actor="user", notes="n/a")
