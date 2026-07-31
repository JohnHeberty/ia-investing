"""Portfolio recommendations API endpoint."""

from __future__ import annotations

import asyncio
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
            all_scores[ticker] = {dim: 0.5 for dim in SCORING_WEIGHTS}

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
