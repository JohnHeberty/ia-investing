"""Unit tests for ia_investing.domain.macro — macro data transforms and validation."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ia_investing.domain.macro import (
    MacroValueRevision,
    TransformedMacroValue,
    macro_definition_hash,
    point_in_time_macro_values,
    resample_macro_values,
    transform_macro_values,
    validate_macro_definition,
    validate_macro_revision,
)


def _rev(
    effective_date: date,
    value: float | None,
    revision: int = 1,
    value_status: str = "reported",
    knowledge_hours: int = 12,
) -> MacroValueRevision:
    return MacroValueRevision(
        effective_date=effective_date,
        revision=revision,
        value=Decimal(str(value)) if value is not None else None,
        value_status=value_status,
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        knowledge_at=datetime(2026, 1, 2, knowledge_hours % 24, tzinfo=UTC),
    )


# ── macro_definition_hash ─────────────────────────────────────────────────────


@pytest.mark.unit
class TestMacroDefinitionHash:
    def test_deterministic(self) -> None:
        h1 = macro_definition_hash({"a": 1, "b": 2})
        h2 = macro_definition_hash({"b": 2, "a": 1})
        assert h1 == h2
        assert len(h1) == 64

    def test_different_values_different_hash(self) -> None:
        h1 = macro_definition_hash({"series": "433"})
        h2 = macro_definition_hash({"series": "434"})
        assert h1 != h2

    def test_empty_payload(self) -> None:
        h = macro_definition_hash({})
        assert len(h) == 64

    def test_nested_dict(self) -> None:
        h = macro_definition_hash({"a": {"b": [1, 2, 3]}})
        assert len(h) == 64


# ── validate_macro_definition ─────────────────────────────────────────────────


@pytest.mark.unit
class TestValidateMacroDefinition:
    def test_valid(self) -> None:
        validate_macro_definition(unit="BRL", frequency="monthly", transformation={"method": "level"})

    def test_empty_unit_raises(self) -> None:
        with pytest.raises(ValueError, match="unit"):
            validate_macro_definition(unit="  ", frequency="monthly", transformation={})

    def test_invalid_frequency_raises(self) -> None:
        with pytest.raises(ValueError, match="frequency"):
            validate_macro_definition(unit="BRL", frequency="hourly", transformation={})

    def test_invalid_method_raises(self) -> None:
        with pytest.raises(ValueError, match="transformation"):
            validate_macro_definition(unit="BRL", frequency="monthly", transformation={"method": "log"})

    def test_invalid_resample_frequency_raises(self) -> None:
        with pytest.raises(ValueError, match="resampling"):
            validate_macro_definition(
                unit="BRL", frequency="monthly",
                transformation={"resample_frequency": "daily"},
            )

    def test_invalid_aggregation_raises(self) -> None:
        with pytest.raises(ValueError, match="aggregation"):
            validate_macro_definition(
                unit="BRL", frequency="monthly",
                transformation={"aggregation": "median"},
            )

    @pytest.mark.parametrize("freq", ["daily", "weekly", "monthly", "quarterly", "annual", "irregular"])
    def test_valid_frequencies(self, freq: str) -> None:
        validate_macro_definition(unit="BRL", frequency=freq, transformation={})

    def test_valid_resample_frequencies(self) -> None:
        for rf in ("monthly", "quarterly", "annual"):
            validate_macro_definition(
                unit="BRL", frequency="monthly",
                transformation={"resample_frequency": rf},
            )

    def test_valid_aggregations(self) -> None:
        for agg in ("last", "sum", "mean"):
            validate_macro_definition(
                unit="BRL", frequency="monthly",
                transformation={"aggregation": agg},
            )


# ── validate_macro_revision ──────────────────────────────────────────────────


@pytest.mark.unit
class TestValidateMacroRevision:
    def test_valid(self) -> None:
        validate_macro_revision(_rev(date(2026, 1, 1), 100))

    def test_zero_revision_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            validate_macro_revision(_rev(date(2026, 1, 1), 100, revision=0))

    def test_naive_timestamps_raise(self) -> None:
        r = MacroValueRevision(
            effective_date=date(2026, 1, 1), revision=1, value=Decimal("100"),
            value_status="reported",
            published_at=datetime(2026, 1, 1),
            knowledge_at=datetime(2026, 1, 2),
        )
        with pytest.raises(ValueError, match="timezone"):
            validate_macro_revision(r)

    def test_knowledge_before_published_raises(self) -> None:
        r = MacroValueRevision(
            effective_date=date(2026, 1, 1), revision=1, value=Decimal("100"),
            value_status="reported",
            published_at=datetime(2026, 1, 5, tzinfo=UTC),
            knowledge_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        with pytest.raises(ValueError, match="knowledge_at"):
            validate_macro_revision(r)

    def test_invalid_status_raises(self) -> None:
        r = _rev(date(2026, 1, 1), 100, value_status="invalid")
        with pytest.raises(ValueError, match="status"):
            validate_macro_revision(r)

    def test_reported_without_value_raises(self) -> None:
        r = _rev(date(2026, 1, 1), None)
        with pytest.raises(ValueError, match="value presence"):
            validate_macro_revision(r)

    def test_missing_with_value_raises(self) -> None:
        r = _rev(date(2026, 1, 1), 100, value_status="missing")
        with pytest.raises(ValueError, match="value presence"):
            validate_macro_revision(r)

    @pytest.mark.parametrize("status", ["reported", "missing", "suppressed", "parse_error"])
    def test_valid_statuses(self, status: str) -> None:
        value = Decimal("100") if status == "reported" else None
        validate_macro_revision(_rev(date(2026, 1, 1), None if value is None else 100, value_status=status))


# ── point_in_time_macro_values ────────────────────────────────────────────────


@pytest.mark.unit
class TestPointInTimeMacroValues:
    def test_filters_by_cutoff(self) -> None:
        r1 = _rev(date(2026, 1, 1), 100, knowledge_hours=10)
        r2 = _rev(date(2026, 2, 1), 200, knowledge_hours=10)
        cutoff = datetime(2026, 1, 2, 10, 30, tzinfo=UTC)
        result = point_in_time_macro_values((r1, r2), cutoff)
        assert len(result) == 2

    def test_excludes_future_knowledge(self) -> None:
        r1 = _rev(date(2026, 1, 1), 100, knowledge_hours=10)
        cutoff = datetime(2026, 1, 2, 9, tzinfo=UTC)
        result = point_in_time_macro_values((r1,), cutoff)
        assert len(result) == 0

    def test_selects_highest_revision(self) -> None:
        r1 = _rev(date(2026, 1, 1), 100, revision=1, knowledge_hours=10)
        r2 = _rev(date(2026, 1, 1), 110, revision=2, knowledge_hours=10)
        cutoff = datetime(2026, 1, 3, tzinfo=UTC)
        result = point_in_time_macro_values((r1, r2), cutoff)
        assert len(result) == 1
        assert result[0].value == Decimal("110")

    def test_naive_cutoff_raises(self) -> None:
        with pytest.raises(ValueError, match="timezone"):
            point_in_time_macro_values((), datetime(2026, 1, 1))

    def test_sorted_by_effective_date(self) -> None:
        r1 = _rev(date(2026, 3, 1), 300, knowledge_hours=10)
        r2 = _rev(date(2026, 1, 1), 100, knowledge_hours=10)
        cutoff = datetime(2026, 1, 3, tzinfo=UTC)
        result = point_in_time_macro_values((r1, r2), cutoff)
        assert result[0].effective_date == date(2026, 1, 1)
        assert result[1].effective_date == date(2026, 3, 1)


# ── transform_macro_values ────────────────────────────────────────────────────


@pytest.mark.unit
class TestTransformMacroValues:
    def test_level_passthrough(self) -> None:
        vals = (_rev(date(2026, 1, 1), 100), _rev(date(2026, 2, 1), 200))
        result = transform_macro_values(vals, "level")
        assert result[0].value == Decimal("100")
        assert result[1].value == Decimal("200")

    def test_difference(self) -> None:
        vals = (_rev(date(2026, 1, 1), 100), _rev(date(2026, 2, 1), 150))
        result = transform_macro_values(vals, "difference")
        assert result[0].value is None
        assert result[1].value == Decimal("50")

    def test_pct_change(self) -> None:
        vals = (_rev(date(2026, 1, 1), 100), _rev(date(2026, 2, 1), 110))
        result = transform_macro_values(vals, "pct_change")
        assert result[0].value is None
        assert result[1].value == Decimal("0.1")

    def test_yoy_lag_12(self) -> None:
        vals = [_rev(date(2025, m, 1), 100) for m in range(1, 13)]
        result = transform_macro_values(tuple(vals), "yoy")
        for r in result:
            assert r.value is None

    def test_invalid_method_raises(self) -> None:
        with pytest.raises(ValueError, match="transformation"):
            transform_macro_values((), "log")

    def test_missing_status_passthrough(self) -> None:
        vals = (_rev(date(2026, 1, 1), None, value_status="missing"),)
        result = transform_macro_values(vals, "level")
        assert result[0].value is None
        assert result[0].value_status == "missing"

    def test_pct_change_division_by_zero(self) -> None:
        vals = (_rev(date(2026, 1, 1), 0), _rev(date(2026, 2, 1), 100))
        result = transform_macro_values(vals, "pct_change")
        assert result[0].value is None
        assert result[1].value is None
        assert result[1].value_status == "parse_error"

    def test_difference_missing_lag(self) -> None:
        vals = (_rev(date(2026, 1, 1), None, value_status="missing"), _rev(date(2026, 2, 1), 100))
        result = transform_macro_values(vals, "difference")
        assert result[1].value is None
        assert result[1].value_status == "missing"


# ── resample_macro_values ─────────────────────────────────────────────────────


@pytest.mark.unit
class TestResampleMacroValues:
    def test_monthly_last(self) -> None:
        vals = (
            TransformedMacroValue(date(2026, 1, 15), Decimal("10"), "reported", 1),
            TransformedMacroValue(date(2026, 1, 20), Decimal("20"), "reported", 1),
        )
        result = resample_macro_values(vals, frequency="monthly", aggregation="last")
        assert len(result) == 1
        assert result[0].value == Decimal("20")

    def test_quarterly_sum(self) -> None:
        vals = (
            TransformedMacroValue(date(2026, 1, 1), Decimal("10"), "reported", 1),
            TransformedMacroValue(date(2026, 2, 1), Decimal("20"), "reported", 1),
            TransformedMacroValue(date(2026, 3, 1), Decimal("30"), "reported", 1),
        )
        result = resample_macro_values(vals, frequency="quarterly", aggregation="sum")
        assert len(result) == 1
        assert result[0].value == Decimal("60")

    def test_annual_mean(self) -> None:
        vals = (
            TransformedMacroValue(date(2026, 1, 1), Decimal("10"), "reported", 1),
            TransformedMacroValue(date(2026, 6, 1), Decimal("20"), "reported", 1),
        )
        result = resample_macro_values(vals, frequency="annual", aggregation="mean")
        assert len(result) == 1
        assert result[0].value == Decimal("15")

    def test_invalid_frequency_raises(self) -> None:
        with pytest.raises(ValueError, match="frequency"):
            resample_macro_values((), frequency="daily", aggregation="last")

    def test_invalid_aggregation_raises(self) -> None:
        with pytest.raises(ValueError, match="aggregation"):
            resample_macro_values((), frequency="monthly", aggregation="median")

    def test_non_reported_passthrough(self) -> None:
        vals = (
            TransformedMacroValue(date(2026, 1, 1), Decimal("10"), "reported", 1),
            TransformedMacroValue(date(2026, 1, 15), None, "missing", 2),
        )
        result = resample_macro_values(vals, frequency="monthly", aggregation="last")
        assert len(result) == 1
        assert result[0].value is None
        assert result[0].value_status == "missing"

    def test_max_source_revision_kept(self) -> None:
        vals = (
            TransformedMacroValue(date(2026, 1, 1), Decimal("10"), "reported", 1),
            TransformedMacroValue(date(2026, 1, 15), Decimal("20"), "reported", 3),
        )
        result = resample_macro_values(vals, frequency="monthly", aggregation="last")
        assert result[0].source_revision == 3
