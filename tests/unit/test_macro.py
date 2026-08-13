"""Unit tests for ia_investing.domain.macro — macro data transforms."""

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


def _rev(effective_date, value, revision=1, value_status="reported", knowledge_hours=12):
    return MacroValueRevision(
        effective_date=effective_date,
        revision=revision,
        value=Decimal(str(value)) if value is not None else None,
        value_status=value_status,
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        knowledge_at=datetime(2026, 1, 2, knowledge_hours % 24, tzinfo=UTC),
    )


@pytest.mark.unit
class TestMacroDefinitionHash:
    def test_deterministic(self):
        h1 = macro_definition_hash({"a": 1, "b": 2})
        h2 = macro_definition_hash({"b": 2, "a": 1})
        assert h1 == h2
        assert len(h1) == 64


@pytest.mark.unit
class TestValidateMacroDefinition:
    def test_valid(self):
        validate_macro_definition(unit="BRL", frequency="monthly", transformation={"method": "level"})

    def test_empty_unit(self):
        with pytest.raises(ValueError, match="unit"):
            validate_macro_definition(unit="  ", frequency="monthly", transformation={})

    def test_invalid_frequency(self):
        with pytest.raises(ValueError, match="frequency"):
            validate_macro_definition(unit="BRL", frequency="hourly", transformation={})

    def test_invalid_method(self):
        with pytest.raises(ValueError, match="transformation"):
            validate_macro_definition(unit="BRL", frequency="monthly", transformation={"method": "log"})

    def test_invalid_resample(self):
        with pytest.raises(ValueError, match="resampling"):
            validate_macro_definition(unit="BRL", frequency="monthly", transformation={"resample_frequency": "daily"})

    def test_invalid_aggregation(self):
        with pytest.raises(ValueError, match="aggregation"):
            validate_macro_definition(unit="BRL", frequency="monthly", transformation={"aggregation": "median"})


@pytest.mark.unit
class TestValidateMacroRevision:
    def test_valid(self):
        validate_macro_revision(_rev(date(2026, 1, 1), 100))

    def test_zero_revision(self):
        with pytest.raises(ValueError, match="positive"):
            validate_macro_revision(_rev(date(2026, 1, 1), 100, revision=0))

    def test_naive_timestamps(self):
        r = MacroValueRevision(
            effective_date=date(2026, 1, 1), revision=1, value=Decimal("100"),
            value_status="reported",
            published_at=datetime(2026, 1, 1),
            knowledge_at=datetime(2026, 1, 2),
        )
        with pytest.raises(ValueError, match="timezone"):
            validate_macro_revision(r)

    def test_knowledge_before_published(self):
        r = MacroValueRevision(
            effective_date=date(2026, 1, 1), revision=1, value=Decimal("100"),
            value_status="reported",
            published_at=datetime(2026, 1, 5, tzinfo=UTC),
            knowledge_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        with pytest.raises(ValueError, match="knowledge_at"):
            validate_macro_revision(r)

    def test_invalid_status(self):
        r = _rev(date(2026, 1, 1), 100, value_status="invalid")
        with pytest.raises(ValueError, match="status"):
            validate_macro_revision(r)

    def test_reported_without_value(self):
        r = _rev(date(2026, 1, 1), None)
        with pytest.raises(ValueError, match="value presence"):
            validate_macro_revision(r)


@pytest.mark.unit
class TestPointInTimeMacroValues:
    def test_filters_by_cutoff(self):
        r1 = _rev(date(2026, 1, 1), 100, knowledge_hours=10)
        r2 = _rev(date(2026, 2, 1), 200, knowledge_hours=10)
        # r1 knowledge_at=Jan 2 10:00, r2 knowledge_at=Jan 2 10:00, cutoff=Jan 2 10:30
        cutoff = datetime(2026, 1, 2, 10, 30, tzinfo=UTC)
        result = point_in_time_macro_values((r1, r2), cutoff)
        assert len(result) == 2
        # Now set cutoff before r2
        cutoff2 = datetime(2026, 1, 2, 9, tzinfo=UTC)
        result2 = point_in_time_macro_values((r1, r2), cutoff2)
        assert len(result2) == 0

    def test_selects_highest_revision(self):
        r1 = _rev(date(2026, 1, 1), 100, revision=1, knowledge_hours=10)
        r2 = _rev(date(2026, 1, 1), 110, revision=2, knowledge_hours=10)
        cutoff = datetime(2026, 1, 3, tzinfo=UTC)
        result = point_in_time_macro_values((r1, r2), cutoff)
        assert len(result) == 1
        assert result[0].value == Decimal("110")

    def test_naive_cutoff_raises(self):
        with pytest.raises(ValueError, match="timezone"):
            point_in_time_macro_values((), datetime(2026, 1, 1))


@pytest.mark.unit
class TestTransformMacroValues:
    def test_level(self):
        vals = (_rev(date(2026, 1, 1), 100), _rev(date(2026, 2, 1), 200))
        result = transform_macro_values(vals, "level")
        assert result[0].value == Decimal("100")
        assert result[1].value == Decimal("200")

    def test_difference(self):
        vals = (_rev(date(2026, 1, 1), 100), _rev(date(2026, 2, 1), 150))
        result = transform_macro_values(vals, "difference")
        assert result[0].value is None  # lag
        assert result[1].value == Decimal("50")

    def test_pct_change(self):
        vals = (_rev(date(2026, 1, 1), Decimal("100")), _rev(date(2026, 2, 1), Decimal("110")))
        result = transform_macro_values(vals, "pct_change")
        assert result[0].value is None
        assert result[1].value == Decimal("0.1")

    def test_yoy(self):
        vals = []
        for year in (2025, 2026):
            for m in range(1, 13):
                vals.append(_rev(date(year, m, 1), 100))
        result = transform_macro_values(tuple(vals), "yoy")
        # First 12 have no lag
        for r in result[:12]:
            assert r.value is None

    def test_invalid_method(self):
        with pytest.raises(ValueError, match="transformation"):
            transform_macro_values((), "log")

    def test_missing_status_passthrough(self):
        vals = (_rev(date(2026, 1, 1), None, value_status="missing"),)
        result = transform_macro_values(vals, "level")
        assert result[0].value is None
        assert result[0].value_status == "missing"


@pytest.mark.unit
class TestResampleMacroValues:
    def test_monthly(self):
        vals = (
            TransformedMacroValue(date(2026, 1, 15), Decimal("10"), "reported", 1),
            TransformedMacroValue(date(2026, 1, 20), Decimal("20"), "reported", 1),
        )
        result = resample_macro_values(vals, frequency="monthly", aggregation="last")
        assert len(result) == 1
        assert result[0].value == Decimal("20")

    def test_quarterly_sum(self):
        vals = (
            TransformedMacroValue(date(2026, 1, 1), Decimal("10"), "reported", 1),
            TransformedMacroValue(date(2026, 2, 1), Decimal("20"), "reported", 1),
            TransformedMacroValue(date(2026, 3, 1), Decimal("30"), "reported", 1),
        )
        result = resample_macro_values(vals, frequency="quarterly", aggregation="sum")
        assert len(result) == 1
        assert result[0].value == Decimal("60")

    def test_annual_mean(self):
        vals = (
            TransformedMacroValue(date(2026, 1, 1), Decimal("10"), "reported", 1),
            TransformedMacroValue(date(2026, 6, 1), Decimal("20"), "reported", 1),
        )
        result = resample_macro_values(vals, frequency="annual", aggregation="mean")
        assert len(result) == 1
        assert result[0].value == Decimal("15")

    def test_invalid_frequency(self):
        with pytest.raises(ValueError, match="frequency"):
            resample_macro_values((), frequency="daily", aggregation="last")

    def test_invalid_aggregation(self):
        with pytest.raises(ValueError, match="aggregation"):
            resample_macro_values((), frequency="monthly", aggregation="median")
