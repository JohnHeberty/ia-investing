from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ia_investing.application.source_registry import SourceRegistryService


class FakeResult:
    def __init__(self, rows: list[tuple[object, object]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[object, object]]:
        return self._rows


class FakeSession:
    def __init__(self, rows: list[tuple[object, object]]) -> None:
        self.rows = rows

    async def execute(self, _statement: object) -> FakeResult:
        return FakeResult(self.rows)


@pytest.mark.asyncio
async def test_source_health_is_sanitized_and_marks_stale() -> None:
    now = datetime(2026, 7, 18, 12, tzinfo=UTC)
    source = SimpleNamespace(
        code="B3",
        name="B3 S.A.",
        schema_version="contract-v1",
        owner_role="data-steward-b3",
        credential_reference="secret://must-never-leak",
        is_active=True,
    )
    sla = SimpleNamespace(
        last_success_at=now - timedelta(days=2),
        last_failure_at=now - timedelta(hours=1),
        expected_frequency_minutes=1440,
        freshness_grace_minutes=60,
        last_error_code="upstream_timeout",
    )

    result = await SourceRegistryService(FakeSession([(source, sla)])).list_health(now)  # type: ignore[arg-type]

    assert result[0].status == "stale"
    assert "credential" not in result[0].model_dump()
    assert result[0].last_error_code == "upstream_timeout"


@pytest.mark.asyncio
async def test_register_source_creates_entities_and_audit() -> None:
    """register_source creates license + source + SLA + audit log."""
    mock_session = AsyncMock()

    async def fake_execute(stmt):
        class FakeResult:
            def scalar_one_or_none(self):
                return None
        return FakeResult()

    mock_session.execute.side_effect = fake_execute
    svc = SourceRegistryService(mock_session)
    await svc.register_source(
        code="test-source",
        name="Test Source",
        owner_role="data-steward",
        license_code="TEST-LICENSE",
        license_name="Test License",
        rate_limit_per_minute=10,
        expected_frequency_minutes=60,
        freshness_grace_minutes=10,
        correlation_id=uuid4(),
    )
    assert mock_session.add.call_count >= 4
    assert mock_session.flush.await_count >= 3


@pytest.mark.asyncio
async def test_update_health_records_success() -> None:
    """update_health with last_success_at updates SLA and emits audit."""
    mock_session = AsyncMock()
    sla_obj = SimpleNamespace(last_success_at=None, last_failure_at=None, last_error_code=None)
    source_obj = SimpleNamespace(id=uuid4(), code="test-source")

    async def fake_execute(stmt):
        class FakeResult:
            def scalar_one_or_none(self):
                return source_obj

        return FakeResult()

    async def fake_execute_sla(stmt):
        class FakeResult:
            def scalar_one_or_none(self):
                return sla_obj

        return FakeResult()

    call_count = 0

    async def routing_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return await fake_execute(stmt)
        return await fake_execute_sla(stmt)

    mock_session.execute.side_effect = routing_execute
    svc = SourceRegistryService(mock_session)
    now = datetime(2026, 7, 19, tzinfo=UTC)
    await svc.update_health("test-source", last_success_at=now, correlation_id=uuid4())
    assert sla_obj.last_success_at == now
    assert mock_session.add.call_count >= 1
