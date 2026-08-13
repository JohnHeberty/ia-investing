from __future__ import annotations

import pytest

from portfolio._scorecard import (
    _SCORECARD_WEIGHTS,
    ScorecardCalculator,
    ScorecardResult,
)


class TestScorecardWeights:
    def test_industrial_weights_sum_to_one(self):
        weights = _SCORECARD_WEIGHTS["industrial"]
        assert sum(weights.values()) == pytest.approx(1.0)

    @pytest.mark.parametrize("scorecard_type", ["industrial", "bank", "utility", "real_estate", "retail"])
    def test_all_types_have_same_keys(self, scorecard_type):
        expected_keys = set(_SCORECARD_WEIGHTS["industrial"].keys())
        actual_keys = set(_SCORECARD_WEIGHTS[scorecard_type].keys())
        assert actual_keys == expected_keys

    @pytest.mark.parametrize("scorecard_type", ["industrial", "bank", "utility", "real_estate", "retail"])
    def test_all_types_weights_sum_to_one(self, scorecard_type):
        weights = _SCORECARD_WEIGHTS[scorecard_type]
        assert sum(weights.values()) == pytest.approx(1.0)


class TestScorecardCalculator:
    def test_industrial_pillar_weights_correct(self):
        calc = ScorecardCalculator()
        metrics = dict.fromkeys(_SCORECARD_WEIGHTS["industrial"], 0.5)
        result = calc.calculate(metrics, "industrial")
        assert isinstance(result, ScorecardResult)
        assert result.scorecard_type == "industrial"
        assert result.overall_score == pytest.approx(0.5, abs=0.01)

    @pytest.mark.parametrize("scorecard_type", ["industrial", "bank", "utility"])
    def test_sector_golden_score_and_missing_never_increase_score(self, scorecard_type):
        calc = ScorecardCalculator()
        complete_metrics = dict.fromkeys(_SCORECARD_WEIGHTS[scorecard_type], 0.5)
        complete = calc.calculate(complete_metrics, scorecard_type)
        missing = calc.calculate({next(iter(_SCORECARD_WEIGHTS[scorecard_type])): 0.5}, scorecard_type)

        assert complete.overall_score == pytest.approx(0.5)
        assert complete.coverage == pytest.approx(1.0)
        assert missing.overall_score <= complete.overall_score
        assert missing.coverage < complete.coverage

    def test_negative_equity_triggers_veto(self):
        calc = ScorecardCalculator()
        metrics = {
            "quality": 0.8,
            "valuation": 0.7,
            "growth": 0.6,
            "leverage": 0.5,
            "momentum": 0.4,
            "dividend": 0.3,
            "total_equity": -100.0,
        }
        result = calc.calculate(metrics, "industrial")
        assert "negative_equity" in result.veto_triggered
        assert result.eligibility == "blocked"

    def test_debt_ebitda_above_5_triggers_veto(self):
        calc = ScorecardCalculator()
        metrics = {
            "quality": 0.8,
            "valuation": 0.7,
            "growth": 0.6,
            "leverage": 0.5,
            "momentum": 0.4,
            "dividend": 0.3,
            "debt_ebitda": 6.0,
        }
        result = calc.calculate(metrics, "industrial")
        assert "debt_ebitda_exceeds_5" in result.veto_triggered
        assert result.eligibility == "blocked"

    def test_no_vetoes_when_clean(self):
        calc = ScorecardCalculator()
        metrics = {
            "quality": 0.8,
            "valuation": 0.7,
            "growth": 0.6,
            "leverage": 0.5,
            "momentum": 0.4,
            "dividend": 0.3,
            "total_equity": 1000.0,
            "debt_ebitda": 2.0,
        }
        result = calc.calculate(metrics, "industrial")
        assert result.veto_triggered == []

    def test_none_metrics_excluded_from_score(self):
        calc = ScorecardCalculator()
        metrics = {
            "quality": None,
            "valuation": 0.8,
            "growth": None,
            "leverage": None,
            "momentum": None,
            "dividend": None,
        }
        result = calc.calculate(metrics, "industrial")
        assert "valuation" in result.pillar_scores
        assert len(result.pillar_scores) == 1
        assert result.overall_score == pytest.approx(0.16)
        assert result.coverage == pytest.approx(0.20)

    def test_missing_does_not_reweight_available_pillars(self):
        calc = ScorecardCalculator()
        incomplete = calc.calculate({"quality": 1.0}, "industrial")
        complete = calc.calculate(dict.fromkeys(_SCORECARD_WEIGHTS["industrial"], 1.0), "industrial")
        assert incomplete.overall_score == pytest.approx(0.25)
        assert complete.overall_score == pytest.approx(1.0)

    def test_custom_weights_override(self):
        custom = {"quality": 1.0}
        calc = ScorecardCalculator(weights=custom)
        metrics = {"quality": 0.9}
        result = calc.calculate(metrics, "industrial")
        assert result.overall_score == pytest.approx(0.9)

    def test_scores_clamped_between_0_and_1(self):
        calc = ScorecardCalculator()
        metrics = {"quality": 2.0, "valuation": -1.0, "growth": 0.5, "leverage": 0.5, "momentum": 0.5, "dividend": 0.5}
        result = calc.calculate(metrics, "industrial")
        for score in result.pillar_scores.values():
            assert 0.0 <= score <= 1.0
