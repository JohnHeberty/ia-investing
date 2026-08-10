"""Portfolio recommendations and theses API endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.security import AuthContext, get_auth_context
from database.core import get_async_session
from ia_investing.agents.portfolio_advisor import (
    SCORING_WEIGHTS,
    build_portfolio_recommendation,
    compute_scores,
    generate_llm_analysis,
)

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio-recommendations"])


class RecommendationResponse(BaseModel):
    portfolio_id: str
    summary: str
    overall_risk: str
    recommendations: list[dict]
    risk_assessment: dict
    performance_outlook: dict
    key_risks: list[str]
    suggested_limits: dict
    llm_analysis: str | None = None


@router.get("/{portfolio_id}/recommendations", response_model=RecommendationResponse)
async def get_portfolio_recommendations(
    portfolio_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> RecommendationResponse:

    from sqlalchemy import text

    result = await session.execute(
        text("""
            SELECT p.id, p.name, p.base_currency,
                   pos.ticker_symbol, pos.quantity, pos.avg_cost_per_share, pos.current_price
            FROM portfolios p
            LEFT JOIN positions pos ON pos.portfolio_id = p.id
            WHERE p.id = :portfolio_id AND p.organization_id = :org_id
        """),
        {"portfolio_id": str(portfolio_id), "org_id": str(auth.organization_id)},
    )

    rows = result.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    from ia_investing.market_data import get_current_prices

    tickers = [row[3] for row in rows if row[3]]
    real_prices = await asyncio.to_thread(get_current_prices, tickers) if tickers else {}

    positions = []
    for row in rows:
        if row[3]:
            ticker = row[3]
            real = real_prices.get(ticker)
            price = real["price"] if real else (float(row[6]) if row[6] else float(row[5]) if row[5] else 0)
            positions.append({
                "ticker_symbol": ticker,
                "quantity": float(row[4]) if row[4] else 0,
                "avg_cost_per_share": float(row[5]) if row[5] else 0,
                "current_price": price,
            })

    all_scores = {}
    for pos in positions:
        ticker = pos["ticker_symbol"]
        try:
            scores = await compute_scores(ticker)
            all_scores[ticker] = scores
        except Exception:
            all_scores[ticker] = dict.fromkeys(SCORING_WEIGHTS, 0.5)

    rec = build_portfolio_recommendation(
        portfolio_id=str(portfolio_id),
        positions=positions,
        all_scores=all_scores,
    )

    avg_momentum = sum(
        scores.get("momentum", 0.5)
        for scores in all_scores.values()
    ) / max(len(all_scores), 1)
    expected_return = 0.03 + (avg_momentum * 0.15)

    llm_result = await generate_llm_analysis(
        positions=positions,
        all_scores=all_scores,
        risk_analysis=rec.risk_assessment,
        expected_return=expected_return,
    )

    for r in rec.recommendations:
        if llm_result and "position_analyses" in llm_result:
            llm_text = llm_result["position_analyses"].get(r.ticker)
            if llm_text:
                r.llm_analysis = llm_text

    return RecommendationResponse(
        portfolio_id=rec.portfolio_id,
        summary=rec.summary,
        overall_risk=rec.overall_risk,
        recommendations=[
            {
                "ticker": r.ticker,
                "action": r.action,
                "current_weight": r.current_weight,
                "target_weight": r.target_weight,
                "confidence": r.confidence,
                "rationale": r.rationale,
                "risk_reward": r.risk_reward,
                "llm_analysis": r.llm_analysis,
                "scores": {
                    dim: round(all_scores.get(r.ticker, {}).get(dim, 0.5), 3)
                    for dim in SCORING_WEIGHTS
                } if all_scores.get(r.ticker) else None,
            }
            for r in rec.recommendations
        ],
        risk_assessment=rec.risk_assessment,
        performance_outlook=rec.performance_outlook,
        key_risks=rec.key_risks,
        suggested_limits=rec.suggested_limits,
        llm_analysis=llm_result.get("portfolio_analysis") if llm_result else None,
    )


# ---------------------------------------------------------------------------
# Portfolio Theses
# ---------------------------------------------------------------------------


class PortfolioThesisItem(BaseModel):
    thesis_id: UUID
    thesis_status: str
    version_id: UUID
    version_number: int
    version_status: str
    summary: str
    recommendation: str
    recommendation_confidence: float
    assumptions: list[dict]
    catalysts: list[dict]
    risks: list[dict]
    invalidation_criteria: list[dict]
    data_as_of: datetime
    expires_at: datetime
    created_by: str
    approved_by: str | None
    approved_at: datetime | None


class PortfolioThesesResponse(BaseModel):
    portfolio_id: str
    theses: list[PortfolioThesisItem]
    count: int


@router.get("/{portfolio_id}/theses", response_model=PortfolioThesesResponse)
async def get_portfolio_theses(
    portfolio_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> PortfolioThesesResponse:

    from sqlalchemy import text

    result = await session.execute(
        text("""
            SELECT DISTINCT ON (rt.id)
                rt.id as thesis_id,
                rt.status as thesis_status,
                rtv.id as version_id,
                rtv.version_number,
                rtv.status as version_status,
                rtv.summary,
                rtv.recommendation,
                rtv.recommendation_confidence,
                rtv.assumptions,
                rtv.catalysts,
                rtv.risks,
                rtv.invalidation_criteria,
                rtv.data_as_of,
                rtv.expires_at,
                rtv.created_by,
                rtv.approved_by,
                rtv.approved_at
            FROM portfolio_version_theses pvt
            JOIN institutional_portfolio_versions ipv ON ipv.id = pvt.portfolio_version_id
            JOIN research_thesis_versions rtv ON rtv.id = pvt.thesis_version_id
            JOIN research_theses rt ON rt.id = rtv.thesis_id
            WHERE ipv.portfolio_id = :portfolio_id
            ORDER BY rt.id, rtv.version_number DESC
        """),
        {"portfolio_id": str(portfolio_id)},
    )

    rows = result.fetchall()

    theses = [
        PortfolioThesisItem(
            thesis_id=row[0],
            thesis_status=row[1],
            version_id=row[2],
            version_number=row[3],
            version_status=row[4],
            summary=row[5],
            recommendation=row[6],
            recommendation_confidence=float(row[7]) if row[7] is not None else 0.0,
            assumptions=row[8] if row[8] else [],
            catalysts=row[9] if row[9] else [],
            risks=row[10] if row[10] else [],
            invalidation_criteria=row[11] if row[11] else [],
            data_as_of=row[12],
            expires_at=row[13],
            created_by=row[14] or "",
            approved_by=row[15],
            approved_at=row[16],
        )
        for row in rows
    ]

    return PortfolioThesesResponse(
        portfolio_id=str(portfolio_id),
        theses=theses,
        count=len(theses),
    )
