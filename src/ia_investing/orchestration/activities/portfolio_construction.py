from __future__ import annotations

from temporalio import activity
from temporalio.exceptions import ApplicationError

from ia_investing.orchestration.activities._telemetry import activity_span
from portfolio._scorecard import ScorecardCalculator, ScorecardResult


@activity.defn(name="run_scorecard")
async def run_scorecard(
    metrics: dict[str, float | None],
    scorecard_type: str,
    data_quality: float,
    thesis_freshness: float,
) -> dict[str, object]:
    """Evaluate instrument eligibility through the multi-pillar scorecard."""
    with activity_span("run_scorecard"):
        try:
            calc = ScorecardCalculator()
            result: ScorecardResult = calc.calculate(
                metrics=metrics,
                scorecard_type=scorecard_type,
                data_quality=data_quality,
                thesis_freshness=thesis_freshness,
            )
        except (ValueError, KeyError) as exc:
            raise ApplicationError(
                f"scorecard evaluation failed: {exc}", type="DataValidationError", non_retryable=True
            ) from exc
        return {
            "pillar_scores": result.pillar_scores,
            "overall_score": result.overall_score,
            "coverage": result.coverage,
            "data_quality": result.data_quality,
            "thesis_freshness": result.thesis_freshness,
            "eligibility": result.eligibility,
            "eligibility_reasons": result.eligibility_reasons,
            "veto_triggered": result.veto_triggered,
            "scorecard_type": result.scorecard_type,
            "definition_version": result.definition_version,
        }


@activity.defn(name="validate_proposal_constraints")
async def validate_proposal_constraints(
    weights: dict[str, float],
    max_weight: float,
    min_weight: float,
    max_sector: float,
    sector_map: dict[str, str] | None,
    min_cash_weight: float,
    max_cash_weight: float,
) -> dict[str, object]:
    """Validate proposed weights against mandate constraints. Returns pass/fail with details."""
    with activity_span("validate_proposal_constraints"):
        issues: list[str] = []
        total = sum(weights.values())
        sector_totals: dict[str, float] = {}
        if abs(total - 1.0) > 0.01:
            issues.append(f"weights_sum_not_one: {total:.6f}")

        for ticker, w in weights.items():
            if w < min_weight - 1e-9:
                issues.append(f"below_min_weight: {ticker}={w:.6f} < {min_weight}")
            if w > max_weight + 1e-9:
                issues.append(f"above_max_weight: {ticker}={w:.6f} > {max_weight}")

        if sector_map:
            for ticker, w in weights.items():
                sector = sector_map.get(ticker, "unknown")
                sector_totals[sector] = sector_totals.get(sector, 0.0) + w
            for sector, total_w in sector_totals.items():
                if total_w > max_sector + 1e-9:
                    issues.append(f"sector_concentration: {sector}={total_w:.6f} > {max_sector}")

        cash_w = weights.get("CASH", 0.0)
        if cash_w < min_cash_weight - 1e-9:
            issues.append(f"below_min_cash: {cash_w:.6f} < {min_cash_weight}")
        if cash_w > max_cash_weight + 1e-9:
            issues.append(f"above_max_cash: {cash_w:.6f} > {max_cash_weight}")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "weights_sum": round(total, 6),
            "sector_totals": {s: round(t, 6) for s, t in sector_totals.items()} if sector_map else {},
        }


PORTFOLIO_CONSTRUCTION_ACTIVITIES = (run_scorecard, validate_proposal_constraints)
