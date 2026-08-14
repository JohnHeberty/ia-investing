"""Unit tests for ia_investing.domain.policy_historical — historical outcome dataset."""

from __future__ import annotations

import pytest

from ia_investing.domain.policy_historical import (
    HISTORICAL_OUTCOMES,
    HistoricalPoliticalOutcome,
    get_historical_outcomes,
)


@pytest.mark.unit
class TestHistoricalOutcomes:
    def test_dataset_has_minimum_samples(self) -> None:
        outcomes = get_historical_outcomes()
        assert len(outcomes) >= 10

    def test_all_outcomes_have_required_fields(self) -> None:
        for outcome in HISTORICAL_OUTCOMES:
            assert outcome.policy_type
            assert outcome.legal_type in ("projeto_lei", "decreto", "normativo", "ato_oficial")
            assert outcome.stage
            assert outcome.source
            assert isinstance(outcome.outcome, bool)

    def test_outcomes_cover_all_legal_types(self) -> None:
        types = {o.legal_type for o in HISTORICAL_OUTCOMES}
        assert types == {"projeto_lei", "decreto", "normativo", "ato_oficial"}

    def test_outcomes_include_both_outcomes(self) -> None:
        outcomes_true = [o for o in HISTORICAL_OUTCOMES if o.outcome]
        outcomes_false = [o for o in HISTORICAL_OUTCOMES if not o.outcome]
        assert len(outcomes_true) >= 5
        assert len(outcomes_false) >= 5

    def test_all_timestamps_are_utc(self) -> None:
        for outcome in HISTORICAL_OUTCOMES:
            assert outcome.predicted_at.tzinfo is not None
            assert outcome.outcome_at.tzinfo is not None

    def test_outcome_at_after_predicted_at(self) -> None:
        for outcome in HISTORICAL_OUTCOMES:
            assert outcome.outcome_at >= outcome.predicted_at

    def test_historical_outcome_is_frozen(self) -> None:
        outcome = HISTORICAL_OUTCOMES[0]
        with pytest.raises(AttributeError):
            outcome.outcome = False  # type: ignore[misc]

    def test_get_historical_outcomes_returns_tuple(self) -> None:
        result = get_historical_outcomes()
        assert isinstance(result, tuple)
        assert all(isinstance(o, HistoricalPoliticalOutcome) for o in result)

    def test_historical_outcomes_count(self) -> None:
        assert len(HISTORICAL_OUTCOMES) == 12
