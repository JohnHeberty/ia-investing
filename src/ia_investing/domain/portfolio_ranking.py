"""Institutional portfolio ranking with explicit eligibility and penalties.

The ranking is intentionally deterministic. AI agents may explain the result, but
must not change the arithmetic or eligibility rules.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from math import isfinite
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ia_investing.application.calibration_engine import CalibrationEngine


class PortfolioStage(StrEnum):
    DRAFT = "draft"
    RESEARCHING = "researching"
    SIMULATED = "simulated"
    COMMITTEE_REVIEW = "committee_review"
    APPROVED = "approved"
    PAPER_LIVE = "paper_live"
    ELIGIBLE_FOR_LIVE = "eligible_for_live"
    LIVE = "live"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


ELIGIBLE_STAGES = {
    PortfolioStage.PAPER_LIVE,
    PortfolioStage.ELIGIBLE_FOR_LIVE,
    PortfolioStage.LIVE,
}


@dataclass(frozen=True, slots=True)
class RankingPolicy:
    minimum_history_days: int = 90
    maximum_data_age_hours: int = 36
    minimum_thesis_coverage: Decimal = Decimal("0.80")
    minimum_data_confidence: Decimal = Decimal("0.85")
    maximum_open_hard_breaches: int = 0
    weights: Mapping[str, Decimal] = field(
        default_factory=lambda: {
            "excess_return": Decimal("0.20"),
            "sortino": Decimal("0.15"),
            "drawdown_control": Decimal("0.15"),
            "regime_stability": Decimal("0.10"),
            "walk_forward_robustness": Decimal("0.10"),
            "risk_compliance": Decimal("0.10"),
            "thesis_health": Decimal("0.10"),
            "cost_capacity": Decimal("0.05"),
            "data_model_confidence": Decimal("0.05"),
        }
    )
    stale_data_penalty: Decimal = Decimal("0.15")
    soft_breach_penalty_each: Decimal = Decimal("0.03")
    expired_thesis_penalty_each: Decimal = Decimal("0.04")
    low_liquidity_penalty: Decimal = Decimal("0.08")
    high_turnover_penalty: Decimal = Decimal("0.06")

    def __post_init__(self) -> None:
        if sum(self.weights.values(), Decimal("0")) != Decimal("1"):
            raise ValueError("ranking weights must sum exactly to 1")
        if self.minimum_history_days < 1:
            raise ValueError("minimum_history_days must be positive")


@dataclass(frozen=True, slots=True)
class PortfolioRankingInput:
    portfolio_id: str
    name: str
    category: str
    benchmark: str
    currency: str
    risk_class: str
    environment: str
    stage: PortfolioStage
    inception_at: datetime
    data_as_of: datetime
    nav_reconciled: bool
    backtest_point_in_time_verified: bool
    approved_version: bool
    open_hard_breaches: int
    open_soft_breaches: int
    expired_theses: int
    thesis_coverage: Decimal
    data_confidence: Decimal
    low_liquidity: bool
    high_turnover: bool
    components: Mapping[str, Decimal]


@dataclass(frozen=True, slots=True)
class RankingResult:
    portfolio_id: str
    cohort_key: str
    eligible: bool
    score: Decimal | None
    component_score: Decimal | None
    penalty: Decimal
    reasons: tuple[str, ...]
    rank: int | None = None


def _bounded(value: Decimal, label: str) -> Decimal:
    if not isfinite(float(value)):
        raise ValueError(f"{label} must be finite")
    if value < 0 or value > 1:
        raise ValueError(f"{label} must be between 0 and 1")
    return value


def cohort_key(item: PortfolioRankingInput) -> str:
    """Only comparable portfolios compete with each other."""
    return "|".join(
        (
            item.category.strip().lower(),
            item.benchmark.strip().upper(),
            item.currency.strip().upper(),
            item.risk_class.strip().lower(),
            item.environment.strip().lower(),
        )
    )


def evaluate_portfolio(
    item: PortfolioRankingInput,
    policy: RankingPolicy,
    *,
    now: datetime | None = None,
) -> RankingResult:
    now = now or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("ranking clock must be timezone-aware")
    for label, value in (("inception_at", item.inception_at), ("data_as_of", item.data_as_of)):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{label} must be timezone-aware")

    reasons: list[str] = []
    if item.data_as_of > now:
        reasons.append("data_as_of_in_future")
    if item.inception_at > now:
        reasons.append("inception_in_future")

    if item.stage not in ELIGIBLE_STAGES:
        reasons.append(f"stage_not_rankable:{item.stage}")
    if not item.nav_reconciled:
        reasons.append("nav_not_reconciled")
    if not item.backtest_point_in_time_verified:
        reasons.append("backtest_not_point_in_time_verified")
    if not item.approved_version:
        reasons.append("no_approved_portfolio_version")
    if item.open_hard_breaches > policy.maximum_open_hard_breaches:
        reasons.append("open_hard_risk_breach")
    if item.thesis_coverage < policy.minimum_thesis_coverage:
        reasons.append("insufficient_thesis_coverage")
    if item.data_confidence < policy.minimum_data_confidence:
        reasons.append("insufficient_data_confidence")
    history_days = (now - item.inception_at).days
    if history_days < policy.minimum_history_days:
        reasons.append("insufficient_track_record")

    missing_components = set(policy.weights) - set(item.components)
    if missing_components:
        reasons.append("missing_components:" + ",".join(sorted(missing_components)))

    if reasons:
        return RankingResult(
            portfolio_id=item.portfolio_id,
            cohort_key=cohort_key(item),
            eligible=False,
            score=None,
            component_score=None,
            penalty=Decimal("0"),
            reasons=tuple(reasons),
        )

    component_score = Decimal("0")
    for component, weight in policy.weights.items():
        component_score += _bounded(item.components[component], component) * weight

    penalty = Decimal("0")
    data_age = now - item.data_as_of
    if data_age > timedelta(hours=policy.maximum_data_age_hours):
        penalty += policy.stale_data_penalty
    penalty += policy.soft_breach_penalty_each * item.open_soft_breaches
    penalty += policy.expired_thesis_penalty_each * item.expired_theses
    if item.low_liquidity:
        penalty += policy.low_liquidity_penalty
    if item.high_turnover:
        penalty += policy.high_turnover_penalty

    score = max(Decimal("0"), component_score - penalty)
    return RankingResult(
        portfolio_id=item.portfolio_id,
        cohort_key=cohort_key(item),
        eligible=True,
        score=score.quantize(Decimal("0.0001")),
        component_score=component_score.quantize(Decimal("0.0001")),
        penalty=penalty.quantize(Decimal("0.0001")),
        reasons=(),
    )


def record_ranking_calibration(
    results: Sequence[RankingResult],
    engine: CalibrationEngine | None = None,
) -> None:
    if engine is None:
        return
    for result in results:
        engine.record_prediction(
            component="portfolio_ranking",
            inputs={"portfolio_id": result.portfolio_id, "cohort_key": result.cohort_key},
            output={
                "eligible": result.eligible,
                "score": str(result.score) if result.score is not None else None,
                "rank": result.rank,
            },
            confidence=float(result.score) if result.score is not None else 0.0,
            tags=["portfolio_ranking"],
        )


def rank_portfolios(
    items: Iterable[PortfolioRankingInput],
    policy: RankingPolicy | None = None,
    *,
    now: datetime | None = None,
) -> list[RankingResult]:
    policy = policy or RankingPolicy()
    evaluated = [evaluate_portfolio(item, policy, now=now) for item in items]
    by_cohort: dict[str, list[RankingResult]] = {}
    for result in evaluated:
        by_cohort.setdefault(result.cohort_key, []).append(result)

    ranked: list[RankingResult] = []
    for key in sorted(by_cohort):
        cohort = by_cohort[key]
        eligible = sorted(
            (result for result in cohort if result.eligible),
            key=lambda result: (-(result.score or Decimal("0")), result.portfolio_id),
        )
        ineligible = sorted(
            (result for result in cohort if not result.eligible),
            key=lambda result: result.portfolio_id,
        )
        ranked.extend(
            RankingResult(
                portfolio_id=result.portfolio_id,
                cohort_key=result.cohort_key,
                eligible=result.eligible,
                score=result.score,
                component_score=result.component_score,
                penalty=result.penalty,
                reasons=result.reasons,
                rank=index,
            )
            for index, result in enumerate(eligible, start=1)
        )
        ranked.extend(ineligible)
    return ranked


def top_x(
    results: Sequence[RankingResult],
    *,
    cohort: str,
    limit: int,
) -> list[RankingResult]:
    if limit < 1:
        raise ValueError("limit must be positive")
    return [
        result
        for result in results
        if result.cohort_key == cohort and result.eligible
    ][:limit]
