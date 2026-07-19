from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

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
