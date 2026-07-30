"""Portfolio recommendations API endpoint."""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.security import AuthContext, get_auth_context
from database.core import get_async_session
from ia_investing.agents.portfolio_advisor import build_portfolio_recommendation, compute_scores

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
    import asyncio

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
            all_scores[ticker] = {"fundamental": 0.5, "momentum": 0.5, "valuation": 0.5, "risk": 0.5, "sentiment": 0.5}

    rec = build_portfolio_recommendation(
        portfolio_id=str(portfolio_id),
        positions=positions,
        all_scores=all_scores,
    )

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
            }
            for r in rec.recommendations
        ],
        risk_assessment=rec.risk_assessment,
        performance_outlook=rec.performance_outlook,
        key_risks=rec.key_risks,
        suggested_limits=rec.suggested_limits,
    )
