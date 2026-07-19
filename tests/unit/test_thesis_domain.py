import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from ia_investing.application.theses import ThesisSnapshot, snapshot_hash, structured_diff


def snapshot(summary: str = "Base") -> ThesisSnapshot:
    now = datetime(2026, 7, 18, tzinfo=UTC)
    return ThesisSnapshot(
        summary=summary,
        assumptions=[{"name": "WACC", "value": "0.10"}],
        catalysts=[{"text": "Crescimento"}],
        risks=[{"text": "Câmbio"}],
        invalidation_criteria=[{"metric": "leverage", "op": ">", "value": "4"}],
        recommendation="buy",
        recommendation_confidence=Decimal("0.80"),
        data_as_of=now,
        expires_at=now + timedelta(days=90),
    )


def test_thesis_snapshot_hash_is_reproducible() -> None:
    assert snapshot_hash(snapshot()) == snapshot_hash(snapshot())


def test_structured_diff_only_contains_changed_fields() -> None:
    diff = structured_diff(snapshot(), snapshot("Revisada"))
    assert set(diff) == {"summary"}
    assert diff["summary"] == {"before": "Base", "after": "Revisada"}


def test_initial_thesis_diff_is_jsonb_serializable() -> None:
    diff = structured_diff(None, snapshot())

    assert json.loads(json.dumps(diff))["recommendation_confidence"]["after"] == "0.80"
    assert diff["data_as_of"]["after"] == "2026-07-18T00:00:00+00:00"
