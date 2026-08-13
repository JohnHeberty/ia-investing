"""Tests for ia_investing.application.metrics — metric calculation service."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ia_investing.application.metrics import (
    MetricBundleV1,
    MetricService,
    calculate_known_metric,
)

# --- calculate_known_metric ---


@pytest.mark.unit
def test_known_metric_current_ratio() -> None:
    result = calculate_known_metric(
        "current_ratio",
        {"current_assets": Decimal("200"), "current_liabilities": Decimal("100")},
    )
    assert result == Decimal("2")


@pytest.mark.unit
def test_known_metric_net_margin() -> None:
    result = calculate_known_metric(
        "net_margin",
        {"net_income": Decimal("50"), "revenue": Decimal("200")},
    )
    assert result == Decimal("0.25")


@pytest.mark.unit
def test_known_metric_debt_to_equity() -> None:
    result = calculate_known_metric(
        "debt_to_equity",
        {"total_debt": Decimal("300"), "equity": Decimal("100")},
    )
    assert result == Decimal("3")


@pytest.mark.unit
def test_known_metric_unregistered_raises() -> None:
    with pytest.raises(ValueError, match="not registered"):
        calculate_known_metric("unknown_metric", {})


@pytest.mark.unit
def test_known_metric_zero_denominator_raises() -> None:
    with pytest.raises(ValueError, match="denominator"):
        calculate_known_metric(
            "current_ratio",
            {"current_assets": Decimal("100"), "current_liabilities": Decimal("0")},
        )


# --- MetricBundleV1 ---


@pytest.mark.unit
def test_metric_bundle_v1_defaults() -> None:
    bundle = MetricBundleV1(
        observation_id=uuid4(),
        issuer_id=uuid4(),
        reporting_period_id=uuid4(),
        metric_name="test",
        definition_version=1,
        formula="x / y",
        unit="ratio",
        value=Decimal("1.5"),
        value_status="calculated",
        data_as_of=datetime.now(UTC),
        quality_score=Decimal("0.9"),
        coverage_ratio=Decimal("1.0"),
        calculation_version="test:v1",
        lineage_ids=[],
    )
    assert bundle.schema_version == "1.0"


@pytest.mark.unit
def test_metric_bundle_v1_forbids_extra() -> None:
    with pytest.raises(Exception):
        MetricBundleV1(
            observation_id=uuid4(),
            issuer_id=uuid4(),
            reporting_period_id=uuid4(),
            metric_name="test",
            definition_version=1,
            formula="x / y",
            unit="ratio",
            value=None,
            value_status="missing",
            data_as_of=datetime.now(UTC),
            quality_score=Decimal("0"),
            coverage_ratio=Decimal("0"),
            calculation_version="test:v1",
            lineage_ids=[],
            extra_field="bad",  # type: ignore[call-arg]
        )


# --- MetricService.calculate ---


def _mock_session() -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())
    session.scalar = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _capture_add_id(obj: object) -> None:
    """Assign a uuid4 to ORM objects missing a real id (post-flush simulation)."""
    if isinstance(getattr(obj, "id", None), MagicMock) or getattr(obj, "id", None) is None:
        obj.id = uuid4()  # type: ignore[union-attr]


def _make_definition(
    name: str = "current_ratio",
    version: int = 1,
    deps: list[str] | None = None,
) -> MagicMock:
    defn = MagicMock()
    defn.id = uuid4()
    defn.name = name
    defn.version = version
    defn.formula = "current_assets / current_liabilities"
    defn.unit = "ratio"
    # Use None sentinel so MagicMock().dependencies returns []
    if deps is None:
        defn.dependencies = ["current_assets", "current_liabilities"]
    else:
        defn.dependencies = deps
    return defn


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_rejects_naive_datetime() -> None:
    session = _mock_session()
    service = MetricService(session)
    with pytest.raises(ValueError, match="timezone"):
        await service.calculate(
            "current_ratio", uuid4(), uuid4(), datetime(2026, 1, 1)
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_definition_not_found() -> None:
    session = _mock_session()
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    service = MetricService(session)
    with pytest.raises(LookupError, match="not found"):
        await service.calculate(
            "current_ratio", uuid4(), uuid4(), datetime.now(UTC)
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_no_dependencies_skips_facts_query() -> None:
    """When definition has no deps, facts query is skipped; usable empty → calculate on empty dict."""
    session = _mock_session()
    defn = _make_definition(deps=[])
    exec1 = MagicMock()
    exec1.scalar_one_or_none.return_value = defn

    session.execute = AsyncMock(side_effect=[exec1])
    session.add = MagicMock(side_effect=_capture_add_id)

    service = MetricService(session)
    # Empty deps + empty usable → len match → tries calculate on empty dict → KeyError
    with pytest.raises(KeyError):
        await service.calculate(
            "current_ratio", uuid4(), uuid4(), datetime.now(UTC)
        )
    # Only 1 execute call (definition); facts query skipped, observation query not reached
    assert session.execute.call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_missing_facts() -> None:
    session = _mock_session()
    defn = _make_definition(deps=["current_assets", "current_liabilities"])

    exec1 = MagicMock()
    exec1.scalar_one_or_none.return_value = defn

    # Facts query returns only 1 of 2 deps
    fact_mock = MagicMock()
    fact_mock.value = Decimal("100")
    fact_mock.value_status = "reported"
    fact_mock.id = uuid4()
    exec2 = MagicMock()
    exec2.all.return_value = [(fact_mock, "current_assets")]

    # Existing observation
    exec3 = MagicMock()
    exec3.scalar_one_or_none.return_value = None

    # Lineage
    exec4 = MagicMock()
    exec4.scalars.return_value = []

    session.execute = AsyncMock(side_effect=[exec1, exec2, exec3, exec4])

    session.add = MagicMock(side_effect=_capture_add_id)

    service = MetricService(session)
    result = await service.calculate(
        "current_ratio", uuid4(), uuid4(), datetime.now(UTC)
    )
    assert result.value is None
    assert result.value_status == "missing"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_full_coverage() -> None:
    session = _mock_session()
    defn = _make_definition(deps=["current_assets", "current_liabilities"])

    exec1 = MagicMock()
    exec1.scalar_one_or_none.return_value = defn

    # Both facts present
    facts = []
    for code in ["current_assets", "current_liabilities"]:
        fact = MagicMock()
        fact.value = Decimal("200") if code == "current_assets" else Decimal("100")
        fact.value_status = "reported"
        fact.id = uuid4()
        facts.append((fact, code))
    exec2 = MagicMock()
    exec2.all.return_value = facts

    # Existing observation
    exec3 = MagicMock()
    exec3.scalar_one_or_none.return_value = None

    # Lineage
    exec4 = MagicMock()
    exec4.scalars.return_value = []

    session.execute = AsyncMock(side_effect=[exec1, exec2, exec3, exec4])

    session.add = MagicMock(side_effect=_capture_add_id)

    service = MetricService(session)
    result = await service.calculate(
        "current_ratio", uuid4(), uuid4(), datetime.now(UTC)
    )
    assert result.value == Decimal("2")
    assert result.value_status == "calculated"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_reuses_existing_observation() -> None:
    session = _mock_session()
    defn = _make_definition(deps=["current_assets", "current_liabilities"])

    exec1 = MagicMock()
    exec1.scalar_one_or_none.return_value = defn

    facts = []
    for code in ["current_assets", "current_liabilities"]:
        fact = MagicMock()
        fact.value = Decimal("200") if code == "current_assets" else Decimal("100")
        fact.value_status = "reported"
        fact.id = uuid4()
        facts.append((fact, code))
    exec2 = MagicMock()
    exec2.all.return_value = facts

    existing = MagicMock()
    existing.id = uuid4()
    existing.value = Decimal("2")
    existing.value_status = "calculated"
    existing.quality_score = Decimal("1")
    existing.coverage_ratio = Decimal("1")
    existing.data_as_of = datetime.now(UTC)
    existing.calculation_version = "current_ratio:v1"
    exec3 = MagicMock()
    exec3.scalar_one_or_none.return_value = existing

    exec4 = MagicMock()
    exec4.scalars.return_value = [uuid4()]

    session.execute = AsyncMock(side_effect=[exec1, exec2, exec3, exec4])

    service = MetricService(session)
    result = await service.calculate(
        "current_ratio", uuid4(), uuid4(), datetime.now(UTC)
    )
    assert result.observation_id == existing.id
    # Should not add new observation
    session.add.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_suppressed_fact_not_usable() -> None:
    session = _mock_session()
    defn = _make_definition(deps=["current_assets", "current_liabilities"])

    exec1 = MagicMock()
    exec1.scalar_one_or_none.return_value = defn

    fact1 = MagicMock()
    fact1.value = Decimal("200")
    fact1.value_status = "reported"
    fact1.id = uuid4()
    fact2 = MagicMock()
    fact2.value = None
    fact2.value_status = "suppressed"
    fact2.id = uuid4()
    exec2 = MagicMock()
    exec2.all.return_value = [(fact1, "current_assets"), (fact2, "current_liabilities")]

    exec3 = MagicMock()
    exec3.scalar_one_or_none.return_value = None
    exec4 = MagicMock()
    exec4.scalars.return_value = []

    session.execute = AsyncMock(side_effect=[exec1, exec2, exec3, exec4])

    session.add = MagicMock(side_effect=_capture_add_id)

    service = MetricService(session)
    result = await service.calculate(
        "current_ratio", uuid4(), uuid4(), datetime.now(UTC)
    )
    assert result.value is None
    assert result.value_status == "missing"
