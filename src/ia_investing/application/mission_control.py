from __future__ import annotations

import logging
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from statistics import quantiles
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ia_investing.contracts.v1 import (
    AgentOperationsSummary,
    CandidatePipelineSummary,
    MissionControlResponse,
    PortfolioRankItem,
    ResearchFunnel,
    RiskSummary,
    SourceHealthItem,
)
from ia_investing.domain.portfolio_ranking import (
    PortfolioRankingInput,
    PortfolioStage,
    RankingPolicy,
    rank_portfolios,
)

logger = logging.getLogger(__name__)

PORTFOLIO_INPUT_SQL = text(
    """
    WITH latest_ranking AS (
        SELECT DISTINCT ON (portfolio_id)
            portfolio_id,
            portfolio_version_id,
            as_of,
            category,
            benchmark,
            risk_class,
            inception_at,
            nav_reconciled,
            backtest_point_in_time_verified,
            approved_version,
            open_hard_breaches,
            open_soft_breaches,
            expired_theses,
            thesis_coverage,
            data_confidence,
            low_liquidity,
            high_turnover,
            excess_return,
            sortino,
            drawdown_control,
            regime_stability,
            walk_forward_robustness,
            risk_compliance,
            thesis_health,
            cost_capacity,
            data_model_confidence
        FROM portfolio_ranking_snapshots
        WHERE as_of <= :as_of
        ORDER BY portfolio_id, as_of DESC, computed_at DESC
    ),
    latest_nav AS (
        SELECT DISTINCT ON (portfolio_id)
            portfolio_id,
            nav,
            as_of,
            reconciled
        FROM nav_publications
        WHERE as_of <= :as_of
        ORDER BY portfolio_id, as_of DESC, revision DESC
    ),
    latest_risk AS (
        SELECT DISTINCT ON (v.portfolio_id)
            v.portfolio_id,
            r.volatility,
            r.drawdown,
            r.as_of
        FROM institutional_risk_snapshots r
        JOIN institutional_portfolio_versions v ON v.id = r.portfolio_version_id
        JOIN model_portfolios p ON p.id = v.portfolio_id
        WHERE p.organization_id = :organization_id
          AND r.as_of <= :as_of
        ORDER BY v.portfolio_id, r.as_of DESC, r.created_at DESC
    )
    SELECT
        p.id AS portfolio_id,
        p.name,
        p.base_currency AS currency,
        p.environment,
        p.state AS stage,
        lr.portfolio_version_id,
        lr.as_of AS ranking_as_of,
        lr.category,
        lr.benchmark,
        lr.risk_class,
        lr.inception_at,
        lr.nav_reconciled,
        lr.backtest_point_in_time_verified,
        lr.approved_version,
        lr.open_hard_breaches,
        lr.open_soft_breaches,
        lr.expired_theses,
        lr.thesis_coverage,
        lr.data_confidence,
        lr.low_liquidity,
        lr.high_turnover,
        lr.excess_return,
        lr.sortino,
        lr.drawdown_control,
        lr.regime_stability,
        lr.walk_forward_robustness,
        lr.risk_compliance,
        lr.thesis_health,
        lr.cost_capacity,
        lr.data_model_confidence,
        ln.nav,
        ln.as_of AS nav_as_of,
        COALESCE(ln.reconciled, FALSE) AS reconciled,
        risk.volatility,
        risk.drawdown
    FROM model_portfolios p
    LEFT JOIN latest_ranking lr ON lr.portfolio_id = p.id
    LEFT JOIN latest_nav ln ON ln.portfolio_id = p.id
    LEFT JOIN latest_risk risk ON risk.portfolio_id = p.id
    WHERE p.organization_id = :organization_id
      AND p.state <> 'archived'
    ORDER BY p.name
    """
)

RESEARCH_FUNNEL_SQL = text(
    """
    SELECT state, count(*) AS count
    FROM research_cases
    WHERE organization_id = :organization_id
    GROUP BY state
    """
)

AGENT_OPS_SQL = text(
    """
    SELECT
        count(*) FILTER (WHERE status IN ('queued', 'running', 'awaiting_approval')) AS running,
        count(*) FILTER (
            WHERE status = 'succeeded' AND created_at >= :since
        ) AS succeeded_24h,
        count(*) FILTER (
            WHERE status = 'failed' AND created_at >= :since
        ) AS failed_24h,
        avg(evidence_coverage) FILTER (
            WHERE status = 'succeeded' AND created_at >= :since
        ) AS evidence_coverage,
        coalesce(sum(cost_usd) FILTER (WHERE created_at >= :since), 0) AS cost_usd_24h,
        array_remove(
            array_agg(duration_ms) FILTER (
                WHERE duration_ms IS NOT NULL AND created_at >= :since
            ),
            NULL
        ) AS durations
    FROM agent_runtime_runs
    WHERE organization_id = :organization_id
    """
)

SOURCE_HEALTH_SQL = text(
    """
    SELECT
        d.id AS source_id,
        d.code,
        d.name,
        s.expected_frequency_minutes,
        s.freshness_grace_minutes,
        s.last_success_at,
        s.last_failure_at,
        s.last_error_code
    FROM data_sources d
    JOIN source_slas s ON s.source_id = d.id
    WHERE d.is_active = TRUE
    ORDER BY d.code
    """
)

RISK_SUMMARY_SQL = text(
    """
    SELECT
        count(*) FILTER (WHERE b.limit_type = 'hard' AND b.status = 'open') AS hard,
        count(*) FILTER (WHERE b.limit_type = 'soft' AND b.status = 'open') AS soft,
        count(DISTINCT v.portfolio_id) FILTER (WHERE b.status = 'open') AS portfolios
    FROM risk_breaches b
    JOIN institutional_risk_snapshots r ON r.id = b.risk_snapshot_id
    JOIN institutional_portfolio_versions v ON v.id = r.portfolio_version_id
    JOIN model_portfolios p ON p.id = v.portfolio_id
    WHERE p.organization_id = :organization_id
    """
)

CANDIDATE_PIPELINE_SQL = text(
    """
    SELECT status, count(*) AS count
    FROM investment_candidates
    WHERE organization_id = :organization_id
    GROUP BY status
    """
)

PENDING_APPROVALS_SQL = text(
    """
    SELECT
        (
            SELECT count(*)
            FROM agent_approval_requests approval
            JOIN agent_runtime_runs run ON run.id = approval.run_id
            WHERE approval.status = 'pending'
              AND run.organization_id = :organization_id
        )
        +
        (
            SELECT count(*)
            FROM model_portfolios
            WHERE state = 'committee_review'
              AND organization_id = :organization_id
        ) AS count
    """
)


def _decimal(value: Any, default: str = "0") -> Decimal:
    return Decimal(str(value)) if value is not None else Decimal(default)


def _p95(values: list[int]) -> int | None:
    clean = sorted(int(value) for value in values if value is not None)
    if not clean:
        return None
    if len(clean) < 20:
        index = max(0, round(0.95 * (len(clean) - 1)))
        return clean[index]
    return int(quantiles(clean, n=100, method="inclusive")[94])


class MissionControlService:
    def __init__(self, session: AsyncSession, policy: RankingPolicy | None = None) -> None:
        self._session = session
        self._policy = policy or RankingPolicy()

    async def build(
        self,
        *,
        organization_id: UUID,
        as_of: datetime | None = None,
        top_limit: int = 20,
    ) -> MissionControlResponse:
        generated_at = datetime.now(UTC)
        as_of = as_of or generated_at
        parameters = {"as_of": as_of, "organization_id": organization_id}
        rows = (await self._session.execute(PORTFOLIO_INPUT_SQL, parameters)).mappings().all()

        inputs: list[PortfolioRankingInput] = []
        by_id: dict[str, dict[str, Any]] = {}
        missing_snapshots: list[PortfolioRankItem] = []
        for row in rows:
            item = dict(row)
            portfolio_id = str(item["portfolio_id"])
            by_id[portfolio_id] = item
            if item["ranking_as_of"] is None:
                missing_snapshots.append(
                    PortfolioRankItem(
                        portfolio_id=UUID(portfolio_id),
                        name=item["name"],
                        cohort_key=(f"unclassified|unknown|{item['currency']}|unknown|{item['environment']}"),
                        category="unclassified",
                        benchmark="unknown",
                        currency=item["currency"],
                        risk_class="unknown",
                        environment=item["environment"],
                        stage=item["stage"],
                        score=None,
                        rank=None,
                        eligible=False,
                        exclusion_reasons=["ranking_snapshot_missing"],
                        nav=item["nav"],
                        nav_as_of=item["nav_as_of"],
                        reconciled=bool(item["reconciled"]),
                        volatility=item["volatility"],
                        drawdown=item["drawdown"],
                        open_hard_breaches=0,
                        open_soft_breaches=0,
                        data_confidence=Decimal("0"),
                        thesis_coverage=Decimal("0"),
                    )
                )
                continue
            inputs.append(
                PortfolioRankingInput(
                    portfolio_id=portfolio_id,
                    name=item["name"],
                    category=item["category"],
                    benchmark=item["benchmark"],
                    currency=item["currency"],
                    risk_class=item["risk_class"],
                    environment=item["environment"],
                    stage=PortfolioStage(item["stage"]),
                    inception_at=item["inception_at"],
                    data_as_of=item["ranking_as_of"],
                    nav_reconciled=bool(item["nav_reconciled"] and item["reconciled"]),
                    backtest_point_in_time_verified=bool(item["backtest_point_in_time_verified"]),
                    approved_version=bool(item["approved_version"]),
                    open_hard_breaches=int(item["open_hard_breaches"]),
                    open_soft_breaches=int(item["open_soft_breaches"]),
                    expired_theses=int(item["expired_theses"]),
                    thesis_coverage=_decimal(item["thesis_coverage"]),
                    data_confidence=_decimal(item["data_confidence"]),
                    low_liquidity=bool(item["low_liquidity"]),
                    high_turnover=bool(item["high_turnover"]),
                    components={
                        "excess_return": _decimal(item["excess_return"]),
                        "sortino": _decimal(item["sortino"]),
                        "drawdown_control": _decimal(item["drawdown_control"]),
                        "regime_stability": _decimal(item["regime_stability"]),
                        "walk_forward_robustness": _decimal(item["walk_forward_robustness"]),
                        "risk_compliance": _decimal(item["risk_compliance"]),
                        "thesis_health": _decimal(item["thesis_health"]),
                        "cost_capacity": _decimal(item["cost_capacity"]),
                        "data_model_confidence": _decimal(item["data_model_confidence"]),
                    },
                )
            )

        ranking_results = rank_portfolios(inputs, self._policy, now=generated_at)
        rank_items = [self._to_contract(result, by_id[result.portfolio_id]) for result in ranking_results]

        eligible_by_cohort: dict[str, list[PortfolioRankItem]] = {}
        for pi in rank_items:
            if pi.eligible:
                eligible_by_cohort.setdefault(pi.cohort_key, []).append(pi)
        eligible: list[PortfolioRankItem] = []
        for key in sorted(eligible_by_cohort):
            eligible.extend(
                sorted(
                    eligible_by_cohort[key],
                    key=lambda item: (item.rank or 10**9, item.name),
                )[:top_limit]
            )
        excluded = sorted(
            [item for item in rank_items if not item.eligible] + missing_snapshots,
            key=lambda item: item.name,
        )

        funnel = await self._research_funnel(organization_id)
        agent_ops = await self._agent_operations(generated_at, organization_id)
        sources = await self._source_health(generated_at)
        candidate_pipeline = await self._candidate_pipeline(organization_id)
        risk = await self._risk_summary(generated_at, organization_id)
        pending = int(await self._session.scalar(PENDING_APPROVALS_SQL, {"organization_id": organization_id}) or 0)
        critical_alerts = risk.open_hard_breaches + sum(
            source.status in {"failed", "stale", "never_succeeded"} for source in sources
        )

        all_portfolio_items = rank_items + missing_snapshots
        data_as_of = max(
            (item.nav_as_of for item in all_portfolio_items if item.nav_as_of is not None),
            default=None,
        )
        return MissionControlResponse(
            generated_at=generated_at,
            data_as_of=data_as_of,
            top_portfolios=eligible,
            excluded_portfolios=excluded,
            research_funnel=funnel,
            agent_operations=agent_ops,
            source_health=sources,
            risk=risk,
            pending_approvals=pending,
            critical_alerts=critical_alerts,
            candidate_pipeline=candidate_pipeline,
        )

    @staticmethod
    def _to_contract(result: Any, row: dict[str, Any]) -> PortfolioRankItem:
        return PortfolioRankItem(
            portfolio_id=UUID(str(row["portfolio_id"])),
            name=row["name"],
            cohort_key=result.cohort_key,
            category=row["category"],
            benchmark=row["benchmark"],
            currency=row["currency"],
            risk_class=row["risk_class"],
            environment=row["environment"],
            stage=row["stage"],
            score=result.score,
            rank=result.rank,
            eligible=result.eligible,
            exclusion_reasons=list(result.reasons),
            nav=row["nav"],
            nav_as_of=row["nav_as_of"],
            reconciled=bool(row["reconciled"]),
            volatility=row["volatility"],
            drawdown=row["drawdown"],
            open_hard_breaches=int(row["open_hard_breaches"]),
            open_soft_breaches=int(row["open_soft_breaches"]),
            data_confidence=_decimal(row["data_confidence"]),
            thesis_coverage=_decimal(row["thesis_coverage"]),
        )

    async def _research_funnel(self, organization_id: UUID) -> ResearchFunnel:
        rows = (
            await self._session.execute(
                RESEARCH_FUNNEL_SQL,
                {"organization_id": organization_id},
            )
        ).mappings()
        counts = Counter({row["state"]: int(row["count"]) for row in rows})
        return ResearchFunnel(**{field: counts[field] for field in ResearchFunnel.model_fields})

    async def _agent_operations(self, now: datetime, organization_id: UUID) -> AgentOperationsSummary:
        row = (
            (
                await self._session.execute(
                    AGENT_OPS_SQL,
                    {
                        "since": now.replace(microsecond=0) - timedelta(hours=24),
                        "organization_id": organization_id,
                    },
                )
            )
            .mappings()
            .one()
        )
        durations = list(row["durations"] or [])
        return AgentOperationsSummary(
            running=int(row["running"] or 0),
            succeeded_24h=int(row["succeeded_24h"] or 0),
            failed_24h=int(row["failed_24h"] or 0),
            schema_pass_rate=None,
            evidence_coverage=row["evidence_coverage"],
            cost_usd_24h=_decimal(row["cost_usd_24h"]),
            p95_duration_ms=_p95(durations),
        )

    async def _source_health(self, now: datetime) -> list[SourceHealthItem]:
        rows = (await self._session.execute(SOURCE_HEALTH_SQL)).mappings().all()
        output: list[SourceHealthItem] = []
        for row in rows:
            last_success = row["last_success_at"]
            max_age = int(row["expected_frequency_minutes"]) + int(row["freshness_grace_minutes"])
            if last_success is None:
                status = "never_succeeded"
                age = None
            else:
                age = max(0, int((now - last_success).total_seconds() // 60))
                if row["last_failure_at"] and row["last_failure_at"] > last_success:
                    status = "failed"
                elif age > max_age:
                    status = "stale"
                else:
                    status = "healthy"
            output.append(
                SourceHealthItem(
                    source_id=row["source_id"],
                    code=row["code"],
                    name=row["name"],
                    status=status,  # type: ignore[arg-type]
                    last_success_at=last_success,
                    last_failure_at=row["last_failure_at"],
                    expected_frequency_minutes=int(row["expected_frequency_minutes"]),
                    freshness_grace_minutes=int(row["freshness_grace_minutes"]),
                    age_minutes=age,
                    error_code=row["last_error_code"],
                )
            )
        return output

    async def _candidate_pipeline(self, organization_id: UUID) -> CandidatePipelineSummary | None:
        try:
            rows = (
                await self._session.execute(
                    CANDIDATE_PIPELINE_SQL,
                    {"organization_id": organization_id},
                )
            ).mappings()
        except Exception:
            logger.warning("investment_candidates table not available; skipping candidate pipeline")
            return None
        counts = {row["status"]: int(row["count"]) for row in rows}
        return CandidatePipelineSummary(
            total=sum(counts.values()),
            awaiting_input=counts.get("awaiting_user_input", 0),
            in_committee=counts.get("committee_review", 0),
            approved=counts.get("approved", 0),
            rejected=counts.get("rejected", 0),
            blocked=counts.get("blocked", 0),
            funnel_by_status=counts,
        )

    async def _risk_summary(self, now: datetime, organization_id: UUID) -> RiskSummary:
        row = (
            (
                await self._session.execute(
                    RISK_SUMMARY_SQL,
                    {"organization_id": organization_id},
                )
            )
            .mappings()
            .one()
        )
        stale = int(
            await self._session.scalar(
                text(
                    """
                    WITH active AS (
                        SELECT id AS portfolio_id
                        FROM model_portfolios
                        WHERE organization_id = :organization_id
                          AND state IN (
                              'committee_review',
                              'approved',
                              'paper_live',
                              'eligible_for_live',
                              'live'
                          )
                    ),
                    latest AS (
                        SELECT DISTINCT ON (v.portfolio_id)
                            v.portfolio_id,
                            r.as_of
                        FROM institutional_risk_snapshots r
                        JOIN institutional_portfolio_versions v ON v.id = r.portfolio_version_id
                        JOIN active a ON a.portfolio_id = v.portfolio_id
                        ORDER BY v.portfolio_id, r.as_of DESC
                    )
                    SELECT count(*)
                    FROM active a
                    LEFT JOIN latest l ON l.portfolio_id = a.portfolio_id
                    WHERE l.as_of IS NULL OR l.as_of < :cutoff
                    """
                ),
                {
                    "cutoff": now - timedelta(hours=36),
                    "organization_id": organization_id,
                },
            )
            or 0
        )
        return RiskSummary(
            open_hard_breaches=int(row["hard"] or 0),
            open_soft_breaches=int(row["soft"] or 0),
            portfolios_with_breaches=int(row["portfolios"] or 0),
            stale_risk_snapshots=stale,
        )
