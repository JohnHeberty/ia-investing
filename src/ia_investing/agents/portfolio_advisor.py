"""Portfolio Advisor Agent.

Recommends adjustments to portfolios based on 9-dimension scoring (fundamental, momentum, valuation, risk, analyst,
leverage, growth, liquidity, earnings) with optional LLM-generated analysis.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
from dataclasses import dataclass, field
from typing import Any

from ia_investing.market_data import (
    get_analyst_data,
    get_fundamentals,
    get_historical_prices,
)

logger = logging.getLogger(__name__)


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
    llm_analysis: str | None = None


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
    llm_portfolio_analysis: str | None = None


SCORING_WEIGHTS = {
    "fundamental": 0.20,
    "momentum": 0.15,
    "valuation": 0.15,
    "risk": 0.10,
    "analyst": 0.12,
    "leverage": 0.08,
    "growth": 0.08,
    "liquidity": 0.05,
    "earnings": 0.07,
}

RISK_THRESHOLDS = {
    "max_single_position": 0.20,
    "max_sector": 0.30,
    "min_cash": 0.05,
    "max_volatility": 0.25,
    "min_sharpe": 0.5,
}


# ---------------------------------------------------------------------------
# Scoring functions — each returns 0.0 .. 1.0
# ---------------------------------------------------------------------------


def _score_fundamental(fund: dict[str, Any]) -> float:
    pe = fund.get("trailing_pe")
    roe = fund.get("return_on_equity")
    div_yield = fund.get("dividend_yield")
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


def _score_valuation(fund: dict[str, Any]) -> float:
    pe = fund.get("trailing_pe")
    forward_pe = fund.get("forward_pe")
    pb = fund.get("price_to_book")
    peg = fund.get("peg_ratio")
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

    if forward_pe is not None and pe is not None and pe > 0:
        growth_premium = (pe - forward_pe) / pe
        if growth_premium > 0.15:
            score += 0.1
        elif growth_premium < -0.10:
            score -= 0.1

    if peg is not None:
        if 0 < peg < 1.0:
            score += 0.1
        elif peg > 2.5:
            score -= 0.1

    return max(0.0, min(1.0, score))


def _score_risk(prices: list[float], fund: dict[str, Any]) -> float:
    score = 0.5

    if len(prices) >= 30:
        returns = [(prices[i] / prices[i - 1] - 1) for i in range(1, len(prices)) if prices[i - 1] > 0]
        if returns:
            mean_ret = sum(returns) / len(returns)
            variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
            volatility = math.sqrt(variance) * math.sqrt(252)

            if volatility < 0.12:
                score = 0.85
            elif volatility < 0.20:
                score = 0.7
            elif volatility < 0.30:
                score = 0.5
            elif volatility < 0.45:
                score = 0.3
            else:
                score = 0.15

    beta = fund.get("beta")
    if beta is not None:
        if beta < 0.6:
            score += 0.1
        elif beta > 1.5:
            score -= 0.15
        elif beta > 1.2:
            score -= 0.05

    fifty_two_high = fund.get("fifty_two_week_high")
    fifty_two_low = fund.get("fifty_two_week_low")
    fund.get("trailing_pe")
    if fifty_two_high and fifty_two_low and fifty_two_high > fifty_two_low:
        high = float(fifty_two_high)
        low = float(fifty_two_low)
        mid = (high + low) / 2
        range_pct = (high - low) / mid if mid > 0 else 0
        if range_pct > 0.6:
            score -= 0.1

    return max(0.0, min(1.0, score))


def _score_analyst(fund: dict[str, Any], analyst: dict[str, Any] | None) -> float:
    score = 0.5
    if not analyst:
        return score

    rec_mean = analyst.get("recommendation_mean") or fund.get("recommendation_mean")
    num_analysts = analyst.get("number_of_analysts") or fund.get("number_of_analyst_opinions")

    if rec_mean is not None:
        if rec_mean <= 1.5:
            score += 0.3
        elif rec_mean <= 2.5:
            score += 0.15
        elif rec_mean >= 4.0:
            score -= 0.25
        elif rec_mean >= 3.5:
            score -= 0.1

    if num_analysts is not None:
        if num_analysts >= 20:
            score += 0.1
        elif num_analysts >= 10:
            score += 0.05
        elif num_analysts < 3:
            score -= 0.1

    target = analyst.get("target_mean_price")
    current_price = analyst.get("current_price")
    if target and current_price and current_price > 0:
        upside = (float(target) - float(current_price)) / float(current_price)
        if upside > 0.20:
            score += 0.15
        elif upside > 0.10:
            score += 0.05
        elif upside < -0.15:
            score -= 0.15
        elif upside < -0.05:
            score -= 0.05

    surprises = analyst.get("last_earnings_surprise")
    if surprises and surprises.get("surprise_percent") is not None:
        sp = float(surprises["surprise_percent"])
        if sp > 10:
            score += 0.1
        elif sp < -10:
            score -= 0.1

    upgrades = analyst.get("recent_upgrades_downgrades", [])
    if upgrades:
        ups = sum(
            1 for u in upgrades if "up" in u.get("action", "").lower() or "upgrade" in u.get("action", "").lower()
        )
        downs = sum(
            1 for u in upgrades if "down" in u.get("action", "").lower() or "downgrade" in u.get("action", "").lower()
        )
        if ups > downs:
            score += 0.05
        elif downs > ups:
            score -= 0.05

    return max(0.0, min(1.0, score))


def _score_leverage(fund: dict[str, Any]) -> float:
    score = 0.5
    dte = fund.get("debt_to_equity")
    current_ratio = fund.get("current_ratio")
    quick_ratio = fund.get("quick_ratio")

    if dte is not None:
        if dte < 50:
            score += 0.2
        elif dte < 100:
            score += 0.1
        elif dte > 200:
            score -= 0.2
        elif dte > 150:
            score -= 0.1

    if current_ratio is not None:
        if current_ratio > 2.0:
            score += 0.15
        elif current_ratio > 1.5:
            score += 0.05
        elif current_ratio < 0.8:
            score -= 0.2
        elif current_ratio < 1.0:
            score -= 0.1

    if quick_ratio is not None:
        if quick_ratio > 1.5:
            score += 0.05
        elif quick_ratio < 0.5:
            score -= 0.1

    fcf = fund.get("free_cashflow")
    ocf = fund.get("operating_cashflow")
    if fcf is not None and ocf is not None and ocf > 0:
        fcf_margin = fcf / ocf
        if fcf_margin > 0.5:
            score += 0.1
        elif fcf_margin < 0:
            score -= 0.1

    return max(0.0, min(1.0, score))


def _score_growth(fund: dict[str, Any]) -> float:
    score = 0.5
    rev_growth = fund.get("revenue_growth")
    earn_growth = fund.get("earnings_growth")
    profit_margins = fund.get("profit_margins")
    operating_margins = fund.get("operating_margins")

    if rev_growth is not None:
        if rev_growth > 0.25:
            score += 0.25
        elif rev_growth > 0.10:
            score += 0.15
        elif rev_growth > 0.02:
            score += 0.05
        elif rev_growth < -0.10:
            score -= 0.2
        elif rev_growth < -0.02:
            score -= 0.1

    if earn_growth is not None:
        if earn_growth > 0.30:
            score += 0.15
        elif earn_growth > 0.10:
            score += 0.05
        elif earn_growth < -0.15:
            score -= 0.15

    if profit_margins is not None:
        if profit_margins > 0.20:
            score += 0.1
        elif profit_margins < 0:
            score -= 0.1

    if operating_margins is not None:
        if operating_margins > 0.25:
            score += 0.05
        elif operating_margins < 0:
            score -= 0.1

    return max(0.0, min(1.0, score))


def _score_liquidity(fund: dict[str, Any]) -> float:
    score = 0.5
    avg_vol = fund.get("avg_volume")
    avg_vol_10d = fund.get("average_volume_10days")
    fund.get("beta")

    if avg_vol is not None and avg_vol > 0:
        if avg_vol > 1_000_000:
            score += 0.2
        elif avg_vol > 100_000:
            score += 0.1
        elif avg_vol < 10_000:
            score -= 0.2

    if avg_vol_10d is not None and avg_vol is not None and avg_vol > 0:
        vol_trend = avg_vol_10d / avg_vol
        if vol_trend > 1.5:
            score += 0.1
        elif vol_trend < 0.5:
            score -= 0.1

    return max(0.0, min(1.0, score))


def _score_earnings(fund: dict[str, Any], analyst: dict[str, Any] | None) -> float:
    score = 0.5
    eqg = fund.get("earnings_quarterly_growth")

    if eqg is not None:
        if eqg > 0.20:
            score += 0.25
        elif eqg > 0.05:
            score += 0.1
        elif eqg < -0.15:
            score -= 0.2
        elif eqg < -0.05:
            score -= 0.1

    if analyst:
        est = analyst.get("earnings_estimate")
        if est and est.get("next_quarter"):
            growth = est["next_quarter"].get("growth")
            if growth is not None:
                if growth > 0.15:
                    score += 0.1
                elif growth < -0.10:
                    score -= 0.1

        surprise = analyst.get("last_earnings_surprise")
        if surprise and surprise.get("surprise_percent") is not None:
            sp = float(surprise["surprise_percent"])
            if sp > 5:
                score += 0.1
            elif sp < -5:
                score -= 0.1

    payout = fund.get("payout_ratio")
    if payout is not None:
        if payout > 1.0:
            score -= 0.15
        elif payout > 0.8:
            score -= 0.05
        elif 0.2 < payout < 0.5:
            score += 0.05

    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Score computation
# ---------------------------------------------------------------------------


async def compute_scores(ticker: str) -> dict[str, Any]:
    """Compute all 9 scoring dimensions for a ticker.

    Returns dict with per-dimension scores (0..1) plus raw fundamentals and analyst data
    for downstream LLM consumption.
    """
    fundamentals_raw, analyst_raw, prices_raw = await asyncio.gather(
        asyncio.to_thread(get_fundamentals, ticker),
        asyncio.to_thread(get_analyst_data, ticker),
        asyncio.to_thread(get_historical_prices, ticker, "1y"),
        return_exceptions=True,
    )

    fund = fundamentals_raw if isinstance(fundamentals_raw, dict) else {}
    analyst = analyst_raw if isinstance(analyst_raw, dict) else None
    hist = prices_raw if isinstance(prices_raw, list) else []
    prices = [h["close"] for h in hist if isinstance(h, dict) and "close" in h]

    return {
        "fundamental": _score_fundamental(fund),
        "momentum": _score_momentum(prices),
        "valuation": _score_valuation(fund),
        "risk": _score_risk(prices, fund),
        "analyst": _score_analyst(fund, analyst),
        "leverage": _score_leverage(fund),
        "growth": _score_growth(fund),
        "liquidity": _score_liquidity(fund),
        "earnings": _score_earnings(fund, analyst),
        "_raw": {"fundamentals": fund, "analyst": analyst, "price_count": len(prices)},
    }


def calculate_position_score(scores: dict[str, float]) -> float:
    total = 0.0
    for dim, weight in SCORING_WEIGHTS.items():
        total += scores.get(dim, 0.5) * weight
    return total


def generate_recommendation(
    ticker: str,
    current_weight: float,
    score: float,
    scores: dict[str, float],
) -> PositionRecommendation:
    risk_score = scores.get("risk", 0.5)
    valuation_score = scores.get("valuation", 0.5)
    momentum_score = scores.get("momentum", 0.5)
    analyst_score = scores.get("analyst", 0.5)
    leverage_score = scores.get("leverage", 0.5)

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
        if analyst_score > 0.6:
            rationale_parts.append("Consenso de analistas favorável")
        if leverage_score > 0.6:
            rationale_parts.append("Balancete saudável")
    elif action in ("sell", "reduce"):
        rationale_parts.append(f"Score composto fraco ({score:.0%})")
        if risk_score < 0.3:
            rationale_parts.append("Volatilidade elevada")
        if momentum_score < 0.35:
            rationale_parts.append("Momentum negativo")
        if leverage_score < 0.3:
            rationale_parts.append("Alavancagem elevada")
        if analyst_score < 0.35:
            rationale_parts.append("Analistas céticos")
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
    hhi = sum(w**2 for w in weights.values())

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
    all_scores: dict[str, dict[str, Any]] | None = None,
) -> PortfolioRecommendation:
    total_value = sum(
        pos.get("quantity", 0) * (pos.get("current_price") or pos.get("avg_cost_per_share", 0)) for pos in positions
    )

    recommendations = []
    for pos in positions:
        ticker = pos.get("ticker_symbol", "")
        price = pos.get("current_price") or pos.get("avg_cost_per_share", 0)
        value = pos.get("quantity", 0) * price
        current_weight = value / total_value if total_value > 0 else 0

        scores = all_scores[ticker] if all_scores and ticker in all_scores else dict.fromkeys(SCORING_WEIGHTS, 0.5)

        composite = calculate_position_score(scores)

        rec = generate_recommendation(
            ticker=ticker,
            current_weight=current_weight,
            score=composite,
            scores=scores,
        )
        recommendations.append(rec)

    risk_analysis = analyze_portfolio_risk(positions, total_value)

    avg_momentum = sum(scores.get("momentum", 0.5) for scores in (all_scores or {}).values()) / max(
        len(all_scores or {}), 1
    )
    expected_return = 0.03 + (avg_momentum * 0.15)

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
            "expected_return_12m": expected_return,
            "scenario_analysis": {"bull": expected_return * 2.5, "base": expected_return, "bear": -expected_return},
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


# ---------------------------------------------------------------------------
# LLM-enhanced analysis
# ---------------------------------------------------------------------------

PORTFOLIO_ADVISOR_SYSTEM_PROMPT = """Você é um consultor de investimentos especializado em análise de
carteiras de ações brasileiras e americanas.

Seu papel é analisar scores quantitativos e dados fundamentais de cada ativo, e gerar uma análise em
linguagem natural que ajude o investidor a tomar decisões informadas.

IMPORTANTE:
- Responda SEMPRE em JSON válido conforme o schema solicitado
- Seja objetivo e direto, baseado nos dados fornecidos
- Não invente dados que não estão no contexto
- Considere o contexto macro brasileiro quando relevante
- Em português do Brasil
"""


def _build_llm_context(
    positions: list[dict[str, Any]],
    all_scores: dict[str, dict[str, Any]],
    risk_analysis: dict[str, Any],
    expected_return: float,
) -> str:
    context_parts = []

    for pos in positions:
        ticker = pos.get("ticker_symbol", "")
        scores = all_scores.get(ticker, {})
        raw = scores.get("_raw", {})
        fund = raw.get("fundamentals", {})
        analyst = raw.get("analyst")

        entry = {
            "ticker": ticker,
            "peso_atual": f"{pos.get('quantity', 0) * pos.get('current_price', 0):.1%}"
            if pos.get("current_price")
            else "N/A",
            "scores": {k: v for k, v in scores.items() if not k.startswith("_")},
            "fundamentals": {
                "nome": fund.get("name"),
                "setor": fund.get("sector"),
                "industria": fund.get("industry"),
                "pe": fund.get("trailing_pe"),
                "forward_pe": fund.get("forward_pe"),
                "peg": fund.get("peg_ratio"),
                "pb": fund.get("price_to_book"),
                "roe": fund.get("return_on_equity"),
                "margem_lucro": fund.get("profit_margins"),
                "crescimento_receita": fund.get("revenue_growth"),
                "crescimento_lucro": fund.get("earnings_growth"),
                "dividend_yield": fund.get("dividend_yield"),
                "debt_to_equity": fund.get("debt_to_equity"),
                "current_ratio": fund.get("current_ratio"),
                "beta": fund.get("beta"),
                "fcf": fund.get("free_cashflow"),
            },
        }

        if analyst:
            entry["analistas"] = {
                "consenso": analyst.get("recommendation_key"),
                "num_analistas": analyst.get("number_of_analysts"),
                "preco_alvo": analyst.get("target_mean_price"),
                "upside": (
                    f"{(analyst['target_mean_price'] - pos.get('current_price', 0)) / pos.get('current_price', 1) * 100:.1f}%"  # noqa: E501
                    if analyst.get("target_mean_price") and pos.get("current_price")
                    else None
                ),
                "surpresa_ultima_earnings": analyst.get("last_earnings_surprise"),
                "recentes_upgrades": analyst.get("recent_upgrades_downgrades", [])[:5],
            }

        context_parts.append(json.dumps(entry, ensure_ascii=False, default=str))

    portfolio_ctx = {
        "risco_portfolio": risk_analysis,
        "retorno_esperado_12m": f"{expected_return:.1%}",
    }

    return f"""## Dados dos Ativos

{chr(10).join(context_parts)}

## Resumo do Portfolio

{json.dumps(portfolio_ctx, ensure_ascii=False, default=str)}"""


async def generate_llm_analysis(
    positions: list[dict[str, Any]],
    all_scores: dict[str, dict[str, Any]],
    risk_analysis: dict[str, Any],
    expected_return: float,
) -> dict[str, Any] | None:
    """Call the LLM to generate natural language analysis for the portfolio.

    Returns {"portfolio_analysis": str, "position_analyses": {ticker: str}} or None on failure.
    """
    try:
        from ia_investing.settings import get_settings

        settings = get_settings()

        if settings.ai.provider == "mock":
            return None

        from ia_investing.ai.gateway import ChatCompletionRequest, ChatMessage, create_gateway_provider

        gw = settings.ai.gateway

        if not gw.base_url or not gw.api_key.get_secret_value():
            logger.info("LLM gateway not configured, skipping LLM analysis")
            return None

        provider = create_gateway_provider(
            provider=gw.provider,
            api_key=gw.api_key.get_secret_value(),
            default_model=gw.model,
            base_url=gw.base_url,
            timeout=min(gw.timeout, 30.0),
            max_retries=1,
        )

        context = _build_llm_context(positions, all_scores, risk_analysis, expected_return)

        user_msg = f"""Analise esta carteira de investimentos e forneça:

1. Uma análise geral do portfólio (máx 3 parágrafos)
2. Para cada ativo, uma análise individual (máx 2 frases cada)

Dados:
{context}

Responda em JSON:
{{
  "portfolio_analysis": "análise geral...",
  "position_analyses": {{
    "TICKER1": "análise...",
    "TICKER2": "análise..."
  }}
}}"""

        request = ChatCompletionRequest(
            messages=[
                ChatMessage(role="system", content=PORTFOLIO_ADVISOR_SYSTEM_PROMPT),
                ChatMessage(role="user", content=user_msg),
            ],
            model=gw.model,
            temperature=0.3,
            max_tokens=2000,
        )

        response = await asyncio.wait_for(
            provider.gateway.chat_completion(request),
            timeout=30.0,
        )
        content = response.content

        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            parsed = json.loads(content[json_start:json_end])
            return parsed if isinstance(parsed, dict) else None

        return None
    except TimeoutError:
        logger.warning("LLM analysis timed out after 30s, falling back to rule-based")
        return None
    except Exception as exc:
        logger.warning("LLM analysis failed, falling back to rule-based: %s", exc)
        return None
