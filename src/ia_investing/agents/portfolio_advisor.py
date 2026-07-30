"""
Portfolio Advisor Agent — recommends adjustments to portfolios based on
fundamental analysis, risk assessment, and market conditions.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from typing import Any

from ia_investing.market_data import get_fundamentals, get_historical_prices


@dataclass
class PositionRecommendation:
    ticker: str
    action: str
    current_weight: float
    target_weight: float
    confidence: float
    rationale: str
    evidence_ids: list[str] = field(default_factory=list)
    stop_loss: float | None = None
    target_price: float | None = None
    risk_reward: float | None = None


@dataclass
class PortfolioRecommendation:
    portfolio_id: str
    summary: str
    overall_risk: str
    recommendations: list[PositionRecommendation]
    risk_assessment: dict[str, Any]
    performance_outlook: dict[str, Any]
    key_risks: list[str]
    suggested_limits: dict[str, Any]


SCORING_WEIGHTS = {
    "fundamental": 0.30,
    "momentum": 0.25,
    "valuation": 0.20,
    "risk": 0.15,
    "sentiment": 0.10,
}

RISK_THRESHOLDS = {
    "max_single_position": 0.20,
    "max_sector": 0.30,
    "min_cash": 0.05,
    "max_volatility": 0.25,
    "min_sharpe": 0.5,
}


def _score_fundamental(fundamentals: dict[str, Any]) -> float:
    pe = fundamentals.get("pe_ratio")
    roe = fundamentals.get("roe")
    div_yield = fundamentals.get("dividend_yield")
    score = 0.5

    if pe is not None:
        if pe < 0:
            score -= 0.2
        elif pe < 10:
            score += 0.2
        elif pe < 20:
            score += 0.1
        elif pe > 50:
            score -= 0.25
        elif pe > 30:
            score -= 0.15

    if roe is not None:
        if roe > 0.20:
            score += 0.15
        elif roe > 0.12:
            score += 0.08
        elif roe < 0.05:
            score -= 0.1

    if div_yield is not None:
        if div_yield > 0.06:
            score += 0.1
        elif div_yield > 0.03:
            score += 0.05

    return max(0.0, min(1.0, score))


def _score_momentum(prices: list[float]) -> float:
    if len(prices) < 20:
        return 0.5

    current = prices[-1]
    price_1m = prices[-22] if len(prices) >= 22 else prices[0]
    price_3m = prices[-66] if len(prices) >= 66 else prices[0]

    ret_1m = (current / price_1m - 1) if price_1m > 0 else 0
    ret_3m = (current / price_3m - 1) if price_3m > 0 else 0

    score = 0.5
    if ret_3m > 0.15:
        score += 0.25
    elif ret_3m > 0.05:
        score += 0.15
    elif ret_3m > 0:
        score += 0.05
    elif ret_3m > -0.10:
        score -= 0.1
    else:
        score -= 0.2

    if ret_1m > 0.05:
        score += 0.1
    elif ret_1m < -0.08:
        score -= 0.15

    return max(0.0, min(1.0, score))


def _score_valuation(fundamentals: dict[str, Any]) -> float:
    pe = fundamentals.get("pe_ratio")
    pb = fundamentals.get("price_to_book")
    score = 0.5

    if pe is not None:
        if pe < 8:
            score += 0.25
        elif pe < 15:
            score += 0.1
        elif pe > 35:
            score -= 0.2
        elif pe > 25:
            score -= 0.1

    if pb is not None:
        if pb < 1.0:
            score += 0.15
        elif pb > 5.0:
            score -= 0.15

    return max(0.0, min(1.0, score))


def _score_risk(prices: list[float]) -> float:
    if len(prices) < 30:
        return 0.5

    returns = [(prices[i] / prices[i - 1] - 1) for i in range(1, len(prices)) if prices[i - 1] > 0]
    if not returns:
        return 0.5

    mean_ret = sum(returns) / len(returns)
    variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
    volatility = math.sqrt(variance) * math.sqrt(252)

    if volatility < 0.12:
        return 0.85
    elif volatility < 0.20:
        return 0.7
    elif volatility < 0.30:
        return 0.5
    elif volatility < 0.45:
        return 0.3
    else:
        return 0.15


async def compute_scores(ticker: str) -> dict[str, float]:
    fundamentals = await asyncio.to_thread(get_fundamentals, ticker)
    hist = await asyncio.to_thread(get_historical_prices, ticker, "1y")
    prices = [h["close"] for h in hist if isinstance(h, dict) and "close" in h]

    fund = fundamentals or {}
    return {
        "fundamental": _score_fundamental(fund),
        "momentum": _score_momentum(prices),
        "valuation": _score_valuation(fund),
        "risk": _score_risk(prices),
        "sentiment": 0.5,
    }


def calculate_position_score(scores: dict[str, float]) -> float:
    return (
        scores["fundamental"] * SCORING_WEIGHTS["fundamental"]
        + scores["momentum"] * SCORING_WEIGHTS["momentum"]
        + scores["valuation"] * SCORING_WEIGHTS["valuation"]
        + scores["risk"] * SCORING_WEIGHTS["risk"]
        + scores["sentiment"] * SCORING_WEIGHTS["sentiment"]
    )


def generate_recommendation(
    ticker: str,
    current_weight: float,
    score: float,
    risk_score: float,
    valuation_score: float,
    momentum_score: float,
) -> PositionRecommendation:
    if score > 0.65 and current_weight < 0.10:
        action = "buy"
        target_weight = min(0.12, current_weight + 0.05)
    elif score > 0.55 and current_weight < 0.15:
        action = "increase"
        target_weight = min(0.18, current_weight + 0.03)
    elif score < 0.35 or (risk_score < 0.25 and current_weight > 0.05):
        action = "sell"
        target_weight = 0.0
    elif score < 0.45 or current_weight > 0.20:
        action = "reduce"
        target_weight = max(0.05, current_weight - 0.03)
    else:
        action = "hold"
        target_weight = current_weight

    confidence = min(max(score, 0.0), 1.0)

    rationale_parts = []
    if action in ("buy", "increase"):
        rationale_parts.append(f"Score composto forte ({score:.0%})")
        if valuation_score > 0.6:
            rationale_parts.append("Valorização atrativa")
        if momentum_score > 0.6:
            rationale_parts.append("Momentum positivo")
    elif action in ("sell", "reduce"):
        rationale_parts.append(f"Score fraco ({score:.0%})")
        if risk_score < 0.3:
            rationale_parts.append("Volatilidade elevada")
        if momentum_score < 0.35:
            rationale_parts.append("Momentum negativo")
    else:
        rationale_parts.append(f"Posição equilibrada (score {score:.0%})")

    risk_reward = None
    if action in ("buy", "increase"):
        risk_reward = 1.5 + (score * 2)
    elif action in ("sell", "reduce"):
        risk_reward = 0.5 + (1 - score)

    return PositionRecommendation(
        ticker=ticker,
        action=action,
        current_weight=current_weight,
        target_weight=round(target_weight, 4),
        confidence=round(confidence, 2),
        rationale=". ".join(rationale_parts),
        risk_reward=round(risk_reward, 1) if risk_reward else None,
    )


def analyze_portfolio_risk(positions: list[dict[str, Any]], total_value: float) -> dict[str, Any]:
    if not positions or total_value == 0:
        return {"concentration_risk": "low", "overall_risk": "low", "max_position_weight": 0}

    weights = {}
    for pos in positions:
        ticker = pos.get("ticker_symbol", "")
        price = pos.get("current_price") or pos.get("avg_cost_per_share", 0)
        value = pos.get("quantity", 0) * price
        weights[ticker] = value / total_value if total_value > 0 else 0

    max_weight = max(weights.values()) if weights else 0
    hhi = sum(w ** 2 for w in weights.values())

    concentration_risk = "high" if max_weight > 0.25 or hhi > 0.25 else "medium" if max_weight > 0.15 else "low"

    return {
        "concentration_risk": concentration_risk,
        "overall_risk": concentration_risk,
        "max_position_weight": round(max_weight, 4),
        "hhi": round(hhi, 4),
    }


def build_portfolio_recommendation(
    portfolio_id: str,
    positions: list[dict[str, Any]],
    all_scores: dict[str, dict[str, float]] | None = None,
) -> PortfolioRecommendation:
    total_value = sum(
        pos.get("quantity", 0) * (pos.get("current_price") or pos.get("avg_cost_per_share", 0))
        for pos in positions
    )

    recommendations = []
    for pos in positions:
        ticker = pos.get("ticker_symbol", "")
        price = pos.get("current_price") or pos.get("avg_cost_per_share", 0)
        value = pos.get("quantity", 0) * price
        current_weight = value / total_value if total_value > 0 else 0

        if all_scores and ticker in all_scores:
            scores = all_scores[ticker]
        else:
            scores = {"fundamental": 0.5, "momentum": 0.5, "valuation": 0.5, "risk": 0.5, "sentiment": 0.5}

        composite = calculate_position_score(scores)

        rec = generate_recommendation(
            ticker=ticker,
            current_weight=current_weight,
            score=composite,
            risk_score=scores["risk"],
            valuation_score=scores["valuation"],
            momentum_score=scores["momentum"],
        )
        recommendations.append(rec)

    risk_analysis = analyze_portfolio_risk(positions, total_value)

    buy_recs = [r for r in recommendations if r.action in ("buy", "increase")]
    sell_recs = [r for r in recommendations if r.action in ("sell", "reduce")]

    summary_parts = []
    if buy_recs:
        summary_parts.append(f"{len(buy_recs)} recomendações de compra")
    if sell_recs:
        summary_parts.append(f"{len(sell_recs)} recomendações de venda")
    hold_recs = [r for r in recommendations if r.action == "hold"]
    if hold_recs:
        summary_parts.append(f"{len(hold_recs)} manter")
    if not summary_parts:
        summary_parts.append("Posições mantidas")

    return PortfolioRecommendation(
        portfolio_id=portfolio_id,
        summary=f"Análise de {len(positions)} posições. {', '.join(summary_parts)}.",
        overall_risk=risk_analysis["overall_risk"],
        recommendations=recommendations,
        risk_assessment=risk_analysis,
        performance_outlook={
            "expected_return_12m": 0.08,
            "scenario_analysis": {"bull": 0.20, "base": 0.08, "bear": -0.08},
        },
        key_risks=[
            risk
            for risk in [
                "Concentração em poucos ativos" if risk_analysis["concentration_risk"] == "high" else None,
            ]
            if risk is not None
        ],
        suggested_limits=RISK_THRESHOLDS,
    )
