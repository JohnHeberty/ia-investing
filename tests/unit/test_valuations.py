"""Unit tests for ValuationService and helpers (valuations.py)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock

import pytest

from database.models.data_governance import QuarantineRecord
from database.models.financial_facts import FinancialFact, MetricObservation
from database.models.research import ResearchEvidence
from database.models.thesis_domain import ResearchThesisVersion
from database.models.valuation import ValuationResult, ValuationRun
from ia_investing.application.valuations import (
    AssumptionInput,
    RelativeInput,
    ReverseDCFInput,
    ScenarioInput,
    ValuationCommand,
    ValuationExecution,
    ValuationService,
    _json_value,
    canonical_payload,
)
from ia_investing.domain.valuation import DCFInput


# ---------------------------------------------------------------------------
# _json_value / canonical_payload pure helpers
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestJsonValue:
    def test_decimal_to_string(self) -> None:
        assert _json_value(Decimal("3.14")) == "3.14"

    def test_uuid_to_string(self) -> None:
        u = uuid4()
        assert _json_value(u) == str(u)

    def test_datetime_to_string(self) -> None:
        dt = datetime(2026, 1, 1, tzinfo=UTC)
        assert _json_value(dt) == str(dt)

    def test_dict_recursive(self) -> None:
        result = _json_value({"a": Decimal("1"), "b": [Decimal("2")]})
        assert result == {"a": "1", "b": ["2"]}

    def test_plain_passthrough(self) -> None:
        assert _json_value("hello") == "hello"
        assert _json_value(42) == 42


@pytest.mark.unit
class TestCanonicalPayload:
    def test_returns_normalized_and_sha256(self) -> None:
        payload = {"x": Decimal("1.0"), "y": uuid4()}
        normalized, sha = canonical_payload(payload)
        assert isinstance(normalized, dict)
        assert len(sha) == 64

    def test_deterministic_hash(self) -> None:
        p1 = {"a": Decimal("1")}
        p2 = {"a": Decimal("1")}
        _, h1 = canonical_payload(p1)
        _, h2 = canonical_payload(p2)
        assert h1 == h2

    def test_rejects_non_dict(self) -> None:
        with pytest.raises(TypeError, match="must be an object"):
            canonical_payload([1, 2, 3])


# ---------------------------------------------------------------------------
# ValuationCommand construction
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestValuationCommandDataclass:
    def test_frozen(self) -> None:
        cmd = _make_command()
        with pytest.raises(AttributeError):
            cmd.code_version = "new"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ValuationService.execute
# ---------------------------------------------------------------------------
def _dcf_input() -> DCFInput:
    return DCFInput(
        free_cash_flows=(Decimal("100"), Decimal("110")),
        discount_rate=Decimal("0.10"),
        terminal_growth=Decimal("0.03"),
        net_debt=Decimal("200"),
        shares_outstanding=Decimal("100"),
    )


def _make_command(*, thesis_data_as_of: datetime | None = None) -> ValuationCommand:
    return ValuationCommand(
        thesis_version_id=uuid4(),
        code_version="v1",
        data_as_of=thesis_data_as_of or datetime(2026, 6, 1, tzinfo=UTC),
        assumptions=(
            AssumptionInput(
                name="fcf_growth",
                value=Decimal("0.05"),
                unit="percent",
                horizon="5y",
                source_type="evidence",
                source_id=uuid4(),
                source_version="ev1",
                approved_by="analyst",
            ),
        ),
        scenarios=(
            ScenarioInput(name="bear", probability=Decimal("0.25"), inputs=_dcf_input()),
            ScenarioInput(name="base", probability=Decimal("0.50"), inputs=_dcf_input()),
            ScenarioInput(name="bull", probability=Decimal("0.25"), inputs=_dcf_input()),
        ),
        relative=RelativeInput(
            metric=Decimal("100"),
            selected_multiple=Decimal("8"),
            net_debt=Decimal("200"),
            shares_outstanding=Decimal("100"),
        ),
        reverse_dcf=ReverseDCFInput(
            market_enterprise_value=Decimal("2000"),
            starting_cash_flow=Decimal("100"),
            discount_rate=Decimal("0.10"),
        ),
    )


@pytest.mark.unit
class TestValuationServiceExecute:
    @pytest.mark.asyncio
    async def test_missing_permission_rejected(self) -> None:
        session = AsyncMock()
        svc = ValuationService(session)
        with pytest.raises(PermissionError, match="valuations:create"):
            await svc.execute(_make_command(), "analyst", frozenset())

    @pytest.mark.asyncio
    async def test_naive_data_as_of_rejected(self) -> None:
        session = AsyncMock()
        svc = ValuationService(session)
        cmd = _make_command()
        cmd = ValuationCommand(
            thesis_version_id=cmd.thesis_version_id,
            code_version=cmd.code_version,
            data_as_of=datetime(2026, 6, 1),
            assumptions=cmd.assumptions,
            scenarios=cmd.scenarios,
            relative=cmd.relative,
            reverse_dcf=cmd.reverse_dcf,
        )
        with pytest.raises(ValueError, match="timezone"):
            await svc.execute(cmd, "analyst", frozenset({"valuations:create"}))

    @pytest.mark.asyncio
    async def test_thesis_not_found(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        svc = ValuationService(session)
        with pytest.raises(LookupError, match="thesis version not found"):
            await svc.execute(_make_command(), "analyst", frozenset({"valuations:create"}))

    @pytest.mark.asyncio
    async def test_thesis_from_future_rejected(self) -> None:
        session = AsyncMock()
        thesis = MagicMock(spec=ResearchThesisVersion)
        thesis.data_as_of = datetime(2027, 1, 1, tzinfo=UTC)
        session.get = AsyncMock(return_value=thesis)
        svc = ValuationService(session)
        with pytest.raises(ValueError, match="future relative to valuation cutoff"):
            await svc.execute(_make_command(), "analyst", frozenset({"valuations:create"}))

    @pytest.mark.asyncio
    async def test_no_assumptions_rejected(self) -> None:
        session = AsyncMock()
        thesis = MagicMock(spec=ResearchThesisVersion)
        thesis.data_as_of = datetime(2025, 1, 1, tzinfo=UTC)
        session.get = AsyncMock(return_value=thesis)
        svc = ValuationService(session)
        cmd = _make_command()
        cmd = ValuationCommand(
            thesis_version_id=cmd.thesis_version_id,
            code_version=cmd.code_version,
            data_as_of=cmd.data_as_of,
            assumptions=(),
            scenarios=cmd.scenarios,
            relative=cmd.relative,
            reverse_dcf=cmd.reverse_dcf,
        )
        with pytest.raises(ValueError, match="at least one"):
            await svc.execute(cmd, "analyst", frozenset({"valuations:create"}))

    @pytest.mark.asyncio
    async def test_duplicate_assumption_names_rejected(self) -> None:
        session = AsyncMock()
        thesis = MagicMock(spec=ResearchThesisVersion)
        thesis.data_as_of = datetime(2025, 1, 1, tzinfo=UTC)
        session.get = AsyncMock(return_value=thesis)
        svc = ValuationService(session)
        cmd = _make_command()
        dup_assumption = AssumptionInput(
            name="fcf_growth",
            value=Decimal("0.10"),
            unit="percent",
            horizon="5y",
            source_type="evidence",
            source_id=uuid4(),
            source_version="ev2",
            approved_by="analyst",
        )
        cmd = ValuationCommand(
            thesis_version_id=cmd.thesis_version_id,
            code_version=cmd.code_version,
            data_as_of=cmd.data_as_of,
            assumptions=(cmd.assumptions[0], dup_assumption),
            scenarios=cmd.scenarios,
            relative=cmd.relative,
            reverse_dcf=cmd.reverse_dcf,
        )
        with pytest.raises(ValueError, match="must be unique"):
            await svc.execute(cmd, "analyst", frozenset({"valuations:create"}))

    @pytest.mark.asyncio
    async def test_evidence_source_not_found(self) -> None:
        session = AsyncMock()
        thesis = MagicMock(spec=ResearchThesisVersion)
        thesis.data_as_of = datetime(2025, 1, 1, tzinfo=UTC)
        session.get = AsyncMock(side_effect=[thesis, None])
        svc = ValuationService(session)
        with pytest.raises(LookupError, match="evidence source not found"):
            await svc.execute(_make_command(), "analyst", frozenset({"valuations:create"}))


# ---------------------------------------------------------------------------
# ValuationService.get
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestValuationServiceGet:
    @pytest.mark.asyncio
    async def test_get_requires_permission(self) -> None:
        session = AsyncMock()
        svc = ValuationService(session)
        with pytest.raises(PermissionError, match="valuations:read"):
            await svc.get(uuid4(), frozenset())

    @pytest.mark.asyncio
    async def test_get_with_research_read(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        svc = ValuationService(session)
        with pytest.raises(LookupError, match="not found"):
            await svc.get(uuid4(), frozenset({"research:read"}))

    @pytest.mark.asyncio
    async def test_get_found(self) -> None:
        session = AsyncMock()
        run = MagicMock(spec=ValuationRun)
        run.id = uuid4()
        session.get = AsyncMock(return_value=run)
        result_mock = MagicMock()
        result_mock.all.return_value = [MagicMock(spec=ValuationResult)]
        session.scalars = AsyncMock(return_value=result_mock)

        svc = ValuationService(session)
        result = await svc.get(run.id, frozenset({"valuations:read"}))
        assert result.replayed is True


# ---------------------------------------------------------------------------
# _validate_assumption_source edge cases
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestValidateAssumptionSource:
    @pytest.mark.asyncio
    async def test_invalid_sensitivity_range(self) -> None:
        session = AsyncMock()
        svc = ValuationService(session)
        assumption = AssumptionInput(
            name="bad",
            value=Decimal("1"),
            unit="pct",
            horizon="5y",
            source_type="evidence",
            source_id=uuid4(),
            source_version="v1",
            approved_by="a",
            sensitivity_low=Decimal("10"),
            sensitivity_high=Decimal("1"),
        )
        with pytest.raises(ValueError, match="invalid sensitivity range"):
            await svc._validate_assumption_source(assumption, datetime.now(UTC))

    @pytest.mark.asyncio
    async def test_evidence_revoked_rejected(self) -> None:
        session = AsyncMock()
        evidence = MagicMock(spec=ResearchEvidence)
        evidence.knowledge_at = datetime(2025, 1, 1, tzinfo=UTC)
        evidence.revoked_at = datetime(2025, 6, 1, tzinfo=UTC)
        evidence.valid_until = None
        session.get = AsyncMock(return_value=evidence)

        svc = ValuationService(session)
        assumption = AssumptionInput(
            name="x", value=Decimal("1"), unit="u", horizon="h",
            source_type="evidence", source_id=uuid4(), source_version="v",
            approved_by="a",
        )
        with pytest.raises(ValueError, match="not valid at cutoff"):
            await svc._validate_assumption_source(assumption, datetime(2025, 12, 1, tzinfo=UTC))

    @pytest.mark.asyncio
    async def test_financial_fact_not_found(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        svc = ValuationService(session)
        assumption = AssumptionInput(
            name="x", value=Decimal("1"), unit="u", horizon="h",
            source_type="financial_fact", source_id=uuid4(), source_version="v",
            approved_by="a",
        )
        with pytest.raises(LookupError, match="financial fact source not found"):
            await svc._validate_assumption_source(assumption, datetime.now(UTC))

    @pytest.mark.asyncio
    async def test_financial_fact_quarantined_rejected(self) -> None:
        session = AsyncMock()
        fact = MagicMock(spec=FinancialFact)
        fact.knowledge_at = datetime(2025, 1, 1, tzinfo=UTC)
        fact.valid_from = datetime(2025, 1, 1, tzinfo=UTC)
        fact.valid_to = datetime(2026, 12, 31, tzinfo=UTC)
        fact.value_status = "reported"
        fact.source_object_version_id = uuid4()
        session.get = AsyncMock(return_value=fact)
        count_mock = MagicMock()
        count_mock.scalar_one.return_value = 1
        session.execute = AsyncMock(return_value=count_mock)

        svc = ValuationService(session)
        assumption = AssumptionInput(
            name="x", value=Decimal("1"), unit="u", horizon="h",
            source_type="financial_fact", source_id=uuid4(), source_version="v",
            approved_by="a",
        )
        with pytest.raises(ValueError, match="quarantined"):
            await svc._validate_assumption_source(assumption, datetime(2025, 12, 1, tzinfo=UTC))

    @pytest.mark.asyncio
    async def test_metric_observation_not_found(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        svc = ValuationService(session)
        assumption = AssumptionInput(
            name="x", value=Decimal("1"), unit="u", horizon="h",
            source_type="metric_observation", source_id=uuid4(), source_version="v",
            approved_by="a",
        )
        with pytest.raises(LookupError, match="metric observation source not found"):
            await svc._validate_assumption_source(assumption, datetime.now(UTC))

    @pytest.mark.asyncio
    async def test_unsupported_source_type(self) -> None:
        session = AsyncMock()
        svc = ValuationService(session)
        assumption = AssumptionInput(
            name="x", value=Decimal("1"), unit="u", horizon="h",
            source_type="unknown_source", source_id=uuid4(), source_version="v",
            approved_by="a",
        )
        with pytest.raises(ValueError, match="unsupported assumption source type"):
            await svc._validate_assumption_source(assumption, datetime.now(UTC))
