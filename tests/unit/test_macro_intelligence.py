from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from ia_investing.domain.macro import (
    MacroValueRevision,
    macro_definition_hash,
    point_in_time_macro_values,
    resample_macro_values,
    transform_macro_values,
    validate_macro_definition,
)


def test_macro_definition_and_hash_are_versionable_and_deterministic() -> None:
    validate_macro_definition(unit="% a.m.", frequency="monthly", transformation={"method": "pct_change"})
    payload = {"series": "433", "unit": "% a.m.", "frequency": "monthly"}
    assert macro_definition_hash(payload) == macro_definition_hash(dict(reversed(payload.items())))
    with pytest.raises(ValueError, match="frequency"):
        validate_macro_definition(unit="BRL", frequency="sometimes", transformation={"method": "level"})


def test_macro_revisions_are_point_in_time_and_never_overwrite_history() -> None:
    cutoff = datetime(2026, 2, 10, tzinfo=UTC)
    revisions = (
        MacroValueRevision(
            date(2026, 1, 1), 1, Decimal("1.2"), "reported", cutoff - timedelta(days=5), cutoff - timedelta(days=5)
        ),
        MacroValueRevision(
            date(2026, 1, 1), 2, Decimal("1.3"), "reported", cutoff + timedelta(days=1), cutoff + timedelta(days=1)
        ),
        MacroValueRevision(
            date(2026, 2, 1), 1, None, "missing", cutoff - timedelta(days=1), cutoff - timedelta(days=1)
        ),
    )
    selected = point_in_time_macro_values(revisions, cutoff)
    assert [(item.effective_date, item.revision, item.value_status) for item in selected] == [
        (date(2026, 1, 1), 1, "reported"),
        (date(2026, 2, 1), 1, "missing"),
    ]
    assert point_in_time_macro_values(revisions, cutoff + timedelta(days=2))[0].revision == 2


def test_macro_transformations_propagate_missing_and_zero_explicitly() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    values = (
        MacroValueRevision(date(2025, 1, 1), 1, Decimal(0), "reported", now, now),
        MacroValueRevision(date(2025, 2, 1), 1, Decimal(10), "reported", now, now),
        MacroValueRevision(date(2025, 3, 1), 1, None, "suppressed", now, now),
    )
    transformed = transform_macro_values(values, "pct_change")
    assert transformed[0].value_status == "missing"
    assert transformed[1].value_status == "parse_error"
    assert transformed[2].value_status == "suppressed"
    assert transform_macro_values(values, "difference")[1].value == Decimal(10)
    monthly = resample_macro_values(transform_macro_values(values, "level"), frequency="monthly", aggregation="last")
    assert monthly[0].value == Decimal(0)
    assert monthly[2].value_status == "suppressed"
