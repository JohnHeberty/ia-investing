from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ScorecardResult:
    pillar_scores: dict[str, float]
    overall_score: float
    coverage: float
    data_quality: float
    thesis_freshness: float
    eligibility: str
    eligibility_reasons: list[str]
    veto_triggered: list[str] = field(default_factory=list)
    scorecard_type: str = "industrial"
    definition_version: str = "scorecard-v1"


_DEFAULT_WEIGHTS: dict[str, float] = {
    "quality": 0.25,
    "valuation": 0.20,
    "growth": 0.15,
    "leverage": 0.15,
    "momentum": 0.10,
    "dividend": 0.15,
}

_SCORECARD_WEIGHTS: dict[str, dict[str, float]] = {
    "industrial": _DEFAULT_WEIGHTS,
    "bank": {
        "quality": 0.20,
        "valuation": 0.15,
        "growth": 0.15,
        "leverage": 0.25,
        "momentum": 0.10,
        "dividend": 0.15,
    },
    "utility": {
        "quality": 0.20,
        "valuation": 0.25,
        "growth": 0.10,
        "leverage": 0.15,
        "momentum": 0.10,
        "dividend": 0.20,
    },
    "real_estate": {
        "quality": 0.15,
        "valuation": 0.30,
        "growth": 0.15,
        "leverage": 0.20,
        "momentum": 0.10,
        "dividend": 0.10,
    },
    "retail": {
        "quality": 0.25,
        "valuation": 0.20,
        "growth": 0.20,
        "leverage": 0.10,
        "momentum": 0.10,
        "dividend": 0.15,
    },
}

_VETO_RULES: dict[str, list[Callable[[dict[str, float | None]], str | None]]] = {
    "bank": [
        lambda m: "current_ratio_below_1" if (v := m.get("current_ratio")) is not None and v < 1.0 else None,
        lambda m: "npl_ratio_exceeds_10pct" if (v := m.get("npl_ratio")) is not None and v > 0.10 else None,
    ],
    "real_estate": [
        lambda m: "ltv_exceeds_70pct" if (v := m.get("ltv")) is not None and v > 0.70 else None,
    ],
}

_EXCLUDED_PILLARS: dict[str, set[str]] = {
    "bank": {"interest_coverage", "roic"},
    "real_estate": {"pe_ratio", "earnings_yield"},
}


class ScorecardCalculator:
    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._custom_weights = weights

    def _get_weights(self, scorecard_type: str) -> dict[str, float]:
        if self._custom_weights:
            return self._custom_weights
        return _SCORECARD_WEIGHTS.get(scorecard_type, _DEFAULT_WEIGHTS)

    def _score_pillar(
        self,
        pillar: str,
        metrics: dict[str, float | None],
        scorecard_type: str,
    ) -> float | None:
        excluded = _EXCLUDED_PILLARS.get(scorecard_type, set())
        if pillar in excluded:
            return None

        value = metrics.get(pillar)
        if value is None:
            return None

        clamped = max(0.0, min(1.0, float(value)))
        return clamped

    def _check_vetoes(self, metrics: dict[str, float | None], scorecard_type: str) -> list[str]:
        vetoes: list[str] = []

        debt_ebitda = metrics.get("debt_ebitda")
        if debt_ebitda is not None and debt_ebitda > 5.0:
            vetoes.append("debt_ebitda_exceeds_5")

        equity = metrics.get("total_equity")
        if equity is not None and equity < 0:
            vetoes.append("negative_equity")

        for rule in _VETO_RULES.get(scorecard_type, []):
            veto = rule(metrics)
            if veto is not None:
                vetoes.append(veto)

        return vetoes

    def calculate(
        self,
        metrics: dict[str, float | None],
        scorecard_type: str = "industrial",
        data_quality: float = 1.0,
        thesis_freshness: float = 1.0,
    ) -> ScorecardResult:
        weights = self._get_weights(scorecard_type)
        if abs(sum(weights.values()) - 1.0) > 1e-9:
            raise ValueError("scorecard weights must sum to one")
        vetoes = self._check_vetoes(metrics, scorecard_type)

        pillar_scores: dict[str, float] = {}
        covered_weight = 0.0
        weighted_sum = 0.0

        for pillar, weight in weights.items():
            score = self._score_pillar(pillar, metrics, scorecard_type)
            if score is not None:
                pillar_scores[pillar] = round(score, 4)
                weighted_sum += score * weight
                covered_weight += weight

        overall = round(weighted_sum, 4)
        eligibility = "blocked" if vetoes else "eligible"

        return ScorecardResult(
            pillar_scores=pillar_scores,
            overall_score=overall,
            coverage=round(covered_weight, 4),
            data_quality=max(0.0, min(1.0, data_quality)),
            thesis_freshness=max(0.0, min(1.0, thesis_freshness)),
            eligibility=eligibility,
            eligibility_reasons=vetoes,
            veto_triggered=vetoes,
            scorecard_type=scorecard_type,
        )
