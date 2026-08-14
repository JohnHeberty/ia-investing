"""Risk overview and macro indicators endpoints.

Exposes real data from institutional_risk_snapshots, risk_breaches,
stress_scenarios, stress_results, macro_indicators, and
institutional_risk_policies.

Note: Macro indicators are global (not org-filtered) because macro data
(SELIC, IPCA, USD/BRL) is shared across all organizations.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.security import AuthContext, get_auth_context
from database.core import get_async_session

logger = logging.getLogger(__name__)

_MAX_SNAPSHOTS = 100

router = APIRouter(prefix="/api/v1/risk", tags=["risk-overview"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RiskBreachItem(BaseModel):
    id: UUID
    limit_name: str
    limit_type: str
    observed_value: float
    limit_value: float
    status: str


class StressScenarioItem(BaseModel):
    id: UUID
    name: str
    pnl_impact: float | None
    nav_impact_ratio: float | None


class RiskSnapshotItem(BaseModel):
    id: UUID
    portfolio_id: str | None
    as_of: datetime
    volatility: float | None
    drawdown: float | None
    concentration: dict | None
    liquidity: dict | None
    exposures: dict | None
    breach_count: int


class RiskOverviewResponse(BaseModel):
    snapshots: list[RiskSnapshotItem]
    breaches: list[RiskBreachItem]
    stress_scenarios: list[StressScenarioItem]
    hard_breach_count: int
    soft_breach_count: int
    latest_volatility: float | None
    latest_drawdown: float | None
    total_snapshots: int


class RiskPolicyItem(BaseModel):
    id: UUID
    mandate_id: str | None
    version: int
    methodology_version: str
    limits: dict
    status: str


class RiskPoliciesResponse(BaseModel):
    policies: list[RiskPolicyItem]
    count: int


class MacroIndicatorItem(BaseModel):
    id: UUID
    indicator_name: str
    source: str
    value: float | None
    unit: str | None
    period_date: datetime | None
    published_at: datetime | None


class MacroIndicatorsResponse(BaseModel):
    indicators: list[MacroIndicatorItem]
    selic: MacroIndicatorItem | None
    ipca: MacroIndicatorItem | None
    usd_brl: MacroIndicatorItem | None
    count: int


# ---------------------------------------------------------------------------
# Risk overview
# ---------------------------------------------------------------------------


@router.get("/overview", response_model=RiskOverviewResponse)
async def get_risk_overview(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> RiskOverviewResponse:

    try:
        snapshots_result = await session.execute(
            text("""
                SELECT DISTINCT ON (v.portfolio_id)
                    s.id, v.portfolio_id::text, s.as_of,
                    s.volatility, s.drawdown,
                    s.concentration, s.liquidity, s.exposures
                FROM institutional_risk_snapshots s
                JOIN institutional_portfolio_versions v ON v.id = s.portfolio_version_id
                JOIN model_portfolios mp ON mp.id = v.portfolio_id
                WHERE mp.organization_id = :org_id
                ORDER BY v.portfolio_id, s.as_of DESC
            """),
            {"org_id": str(auth.organization_id)},
        )
        snapshot_rows = snapshots_result.fetchall()
    except Exception:
        logger.exception("Failed to fetch risk snapshots for org %s", auth.organization_id)
        raise HTTPException(status_code=500, detail="Failed to load risk data") from None

    snapshots = []
    snapshot_ids = []
    for row in snapshot_rows:
        sid = row[0]
        snapshot_ids.append(sid)
        snapshots.append(
            RiskSnapshotItem(
                id=sid,
                portfolio_id=row[1],
                as_of=row[2],
                volatility=float(row[3]) if row[3] is not None else None,
                drawdown=float(row[4]) if row[4] is not None else None,
                concentration=row[5],
                liquidity=row[6],
                exposures=row[7],
                breach_count=0,
            )
        )

    snapshot_ids = snapshot_ids[:_MAX_SNAPSHOTS]

    async def _fetch_breaches() -> list[dict]:
        if not snapshot_ids:
            return []
        result = await session.execute(
            text("""
                SELECT id, risk_snapshot_id, limit_name, limit_type,
                       observed_value, limit_value, status
                FROM risk_breaches
                WHERE risk_snapshot_id = ANY(:snapshot_ids::uuid[])
                ORDER BY created_at DESC
            """),
            {"snapshot_ids": [str(sid) for sid in snapshot_ids]},
        )
        return [
            {
                "id": row[0],
                "snapshot_id": row[1],
                "limit_name": row[2],
                "limit_type": row[3],
                "observed_value": float(row[4]) if row[4] is not None else 0,
                "limit_value": float(row[5]) if row[5] is not None else 0,
                "status": row[6],
            }
            for row in result.fetchall()
        ]

    async def _fetch_stress() -> list[dict]:
        result = await session.execute(
            text("""
                SELECT sr.id, ss.logical_id, sr.pnl_impact, sr.nav_impact_ratio
                FROM stress_results sr
                JOIN stress_scenarios ss ON ss.id = sr.scenario_id
                JOIN institutional_risk_snapshots s ON s.id = sr.risk_snapshot_id
                JOIN institutional_portfolio_versions v ON v.id = s.portfolio_version_id
                JOIN model_portfolios mp ON mp.id = v.portfolio_id
                WHERE mp.organization_id = :org_id
                ORDER BY sr.id DESC
                LIMIT 20
            """),
            {"org_id": str(auth.organization_id)},
        )
        return [
            {
                "id": row[0],
                "name": row[1],
                "pnl_impact": float(row[2]) if row[2] is not None else None,
                "nav_impact_ratio": float(row[3]) if row[3] is not None else None,
            }
            for row in result.fetchall()
        ]

    try:
        breach_rows, stress_rows = await asyncio.gather(
            _fetch_breaches(),
            _fetch_stress(),
        )
    except Exception:
        logger.exception("Failed to fetch breaches/stress for org %s", auth.organization_id)
        breach_rows, stress_rows = [], []

    breach_by_snapshot: dict[UUID, int] = {}
    for b in breach_rows:
        sid = b["snapshot_id"]
        breach_by_snapshot[sid] = breach_by_snapshot.get(sid, 0) + 1

    breaches = []
    for snap in snapshots:
        snap.breach_count = breach_by_snapshot.get(snap.id, 0)
        for b in breach_rows:
            if b["snapshot_id"] == snap.id:
                breaches.append(
                    RiskBreachItem(
                        id=b["id"],
                        limit_name=b["limit_name"],
                        limit_type=b["limit_type"],
                        observed_value=b["observed_value"],
                        limit_value=b["limit_value"],
                        status=b["status"],
                    )
                )

    hard_breaches = [b for b in breaches if b.limit_type == "hard" and b.status == "open"]
    soft_breaches = [b for b in breaches if b.limit_type == "soft" and b.status == "open"]

    stress_scenarios = [
        StressScenarioItem(
            id=s["id"],
            name=s["name"],
            pnl_impact=s["pnl_impact"],
            nav_impact_ratio=s["nav_impact_ratio"],
        )
        for s in stress_rows
    ]

    latest_volatility = snapshots[0].volatility if snapshots else None
    latest_drawdown = snapshots[0].drawdown if snapshots else None

    return RiskOverviewResponse(
        snapshots=snapshots,
        breaches=breaches,
        stress_scenarios=stress_scenarios,
        hard_breach_count=len(hard_breaches),
        soft_breach_count=len(soft_breaches),
        latest_volatility=latest_volatility,
        latest_drawdown=latest_drawdown,
        total_snapshots=len(snapshots),
    )


# ---------------------------------------------------------------------------
# Risk policies (configurable limits)
# ---------------------------------------------------------------------------


@router.get("/policies", response_model=RiskPoliciesResponse)
async def get_risk_policies(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> RiskPoliciesResponse:

    try:
        result = await session.execute(
            text("""
                SELECT rp.id, rp.mandate_id::text, rp.version,
                       rp.methodology_version, rp.limits, rp.status
                FROM institutional_risk_policies rp
                JOIN strategy_mandates sm ON sm.id = rp.mandate_id
                WHERE sm.organization_id = :org_id
                ORDER BY rp.version DESC
                LIMIT 10
            """),
            {"org_id": str(auth.organization_id)},
        )

        policies = [
            RiskPolicyItem(
                id=row[0],
                mandate_id=row[1],
                version=row[2],
                methodology_version=row[3],
                limits=row[4] or {},
                status=row[5],
            )
            for row in result.fetchall()
        ]
    except Exception:
        logger.exception("Failed to fetch risk policies for org %s", auth.organization_id)
        policies = []

    return RiskPoliciesResponse(policies=policies, count=len(policies))


# ---------------------------------------------------------------------------
# Macro indicators
# ---------------------------------------------------------------------------


@router.get("/macro", response_model=MacroIndicatorsResponse)
async def get_macro_indicators(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> MacroIndicatorsResponse:

    try:
        result = await session.execute(
            text("""
                SELECT DISTINCT ON (indicator_name)
                    id, indicator_name, source, value, unit, period_date, published_at
                FROM macro_indicators
                ORDER BY indicator_name, period_date DESC
            """),
        )

        indicators = [
            MacroIndicatorItem(
                id=row[0],
                indicator_name=row[1],
                source=row[2],
                value=float(row[3]) if row[3] is not None else None,
                unit=row[4],
                period_date=row[5],
                published_at=row[6],
            )
            for row in result.fetchall()
        ]
    except Exception:
        logger.exception("Failed to fetch macro indicators")
        indicators = []

    def _find(patterns: list[str]) -> MacroIndicatorItem | None:
        for ind in indicators:
            name_lower = ind.indicator_name.lower()
            for p in patterns:
                if p in name_lower:
                    return ind
        return None

    return MacroIndicatorsResponse(
        indicators=indicators,
        selic=_find(["selic", "taxa selic", "copom"]),
        ipca=_find(["ipca", "inflação"]),
        usd_brl=_find(["usd", "dólar", "usdbrl", "usd/blr"]),
        count=len(indicators),
    )
