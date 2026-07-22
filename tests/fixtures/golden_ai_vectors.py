from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AITestVector:
    scenario: str
    expected_input_pattern: str
    mock_response: dict[str, Any]
    expected_parsed_output: dict[str, Any]


AI_TEST_VECTORS: list[AITestVector] = [
    AITestVector(
        scenario="thesis_analysis",
        expected_input_pattern="Analise a tese de investimento para {ticker}",
        mock_response={
            "ticker": "PETR4",
            "thesis_title": "Petrobras: Geração de caixa com petróleo acima do breakeven",
            "analysis": (
                "A Petrobras apresenta forte geração de caixa operacional com o Brent acima "
                "de US$ 70/bbl. O dividend yield estimado é de 8.5% para os próximos 12 meses. "
                "O plano de investimentos 2026-2030 prevê CAPEX de US$ 11 bilhões anuais, "
                "focado em águas profundas."
            ),
            "evidence": [
                "Brent a US$ 78/bbl (média 12 meses)",
                "Dívida bruta/US$ 26 bi (menor nível desde 2014)",
                "Produção média de 2.8 MMboe/d no 2T26",
            ],
            "conviction_score": 0.85,
            "risks": [
                "Risco regulatório (preços dos combustíveis)",
                "Transição energética de longo prazo",
                "Exposição política a indicações para o conselho",
            ],
            "catalysts": [
                "Resultado 3T26 (agosto)",
                "Dividendo extraordinário esperado",
                "Nova descoberta na Margem Equatorial",
            ],
            "recommendation": "buy",
            "timeframe": "12m",
        },
        expected_parsed_output={
            "ticker": "PETR4",
            "conviction_score": 0.85,
            "recommendation": "buy",
            "evidence_count": 3,
            "risk_count": 3,
            "catalyst_count": 3,
        },
    ),
    AITestVector(
        scenario="portfolio_rebalance",
        expected_input_pattern="Recomende rebalanceamento para o portfolio {portfolio_id}",
        mock_response={
            "portfolio_id": "pf-finance",
            "current_nav": 1_250_000_000,
            "recommended_actions": [
                {
                    "ticker": "ITUB4",
                    "action": "reduce",
                    "current_weight": 0.25,
                    "target_weight": 0.22,
                    "value_change": -37_500_000,
                    "reason": "Redução de exposição após alta significativa",
                },
                {
                    "ticker": "BPAC11",
                    "action": "increase",
                    "current_weight": 0.15,
                    "target_weight": 0.20,
                    "value_change": 62_500_000,
                    "reason": "Aumento em BTG Pactual devido a crescimento consistente",
                },
                {
                    "ticker": "CASH",
                    "action": "reduce",
                    "current_weight": 0.10,
                    "target_weight": 0.05,
                    "value_change": -62_500_000,
                    "reason": "Realocação de caixa excedente para posições ativas",
                },
            ],
            "expected_turnover": 0.125,
            "estimated_costs": 156_250,
            "rebalance_priority": "high",
            "market_conditions": "favoravel",
        },
        expected_parsed_output={
            "portfolio_id": "pf-finance",
            "actions_count": 3,
            "expected_turnover": 0.125,
            "net_cash_impact": -37_500_000,
            "priority": "high",
        },
    ),
    AITestVector(
        scenario="compliance_check_pass",
        expected_input_pattern="Execute auditoria de compliance para {portfolio_id}",
        mock_response={
            "portfolio_id": "pf-energy",
            "check_timestamp": "2026-07-21T14:30:00Z",
            "status": "passed",
            "checks": [
                {
                    "rule": "concentration_limit",
                    "result": "passed",
                    "detail": "Maior posição (PETR4) em 30% dentro do limite de 35%",
                    "observed_value": 0.30,
                    "limit_value": 0.35,
                },
                {
                    "rule": "sector_exposure",
                    "result": "passed",
                    "detail": "Exposição setorial de 82% dentro do limite de 90%",
                    "observed_value": 0.82,
                    "limit_value": 0.90,
                },
                {
                    "rule": "cash_position",
                    "result": "passed",
                    "detail": "Caixa de 8% dentro do range permitido (5%-15%)",
                    "observed_value": 0.08,
                    "limit_value": None,
                },
                {
                    "rule": "volatility_limit",
                    "result": "passed",
                    "detail": "Volatilidade anualizada de 18.3% dentro do limite de 22%",
                    "observed_value": 0.183,
                    "limit_value": 0.22,
                },
            ],
            "open_breaches": 0,
            "waived_breaches": 0,
        },
        expected_parsed_output={
            "portfolio_id": "pf-energy",
            "status": "passed",
            "checks_passed": 4,
            "checks_failed": 0,
            "open_breaches": 0,
        },
    ),
    AITestVector(
        scenario="compliance_check_fail",
        expected_input_pattern="Execute auditoria de compliance para {portfolio_id}",
        mock_response={
            "portfolio_id": "pf-extreme",
            "check_timestamp": "2026-07-21T14:30:00Z",
            "status": "failed",
            "checks": [
                {
                    "rule": "concentration_limit",
                    "result": "failed",
                    "detail": "Maior posição (PRIO3) em 30% excede limite de 25%",
                    "observed_value": 0.30,
                    "limit_value": 0.25,
                },
                {
                    "rule": "volatility_limit",
                    "result": "failed",
                    "detail": "Volatilidade anualizada de 38.2% excede limite de 30%",
                    "observed_value": 0.382,
                    "limit_value": 0.30,
                },
                {
                    "rule": "sector_exposure",
                    "result": "warning",
                    "detail": "Alta concentração intersetorial sem hedge adequado",
                    "observed_value": None,
                    "limit_value": None,
                },
            ],
            "open_breaches": 2,
            "waived_breaches": 0,
            "recommendations": [
                "Reduzir PRIO3 para no máximo 25%",
                "Implementar hedge de volatilidade",
                "Diversificar entre setores",
            ],
        },
        expected_parsed_output={
            "portfolio_id": "pf-extreme",
            "status": "failed",
            "checks_failed": 2,
            "checks_warning": 1,
            "open_breaches": 2,
        },
    ),
    AITestVector(
        scenario="market_analysis",
        expected_input_pattern="Produza resumo de análise de mercado para {sector}",
        mock_response={
            "sector": "energy",
            "period": "2026-07-01 a 2026-07-21",
            "summary": (
                "O setor de energia apresentou desempenho misto no mês. O petróleo Brent "
                "oscilou entre US$ 75 e US$ 80/bbl, sustentado por cortes da OPEP+ e "
                "demanda global estável. No Brasil, a Petrobras anunciou redução de 2% "
                "no diesel, gerando pressão nas margens de refino. O setor elétrico "
                "beneficiou-se do início do período seco, com expectativa de acionamento "
                "térmico."
            ),
            "index_performance": {
                "IEE": {"change_pct": 1.8, "ytd_pct": 4.2},
                "IBOV": {"change_pct": -0.5, "ytd_pct": 3.1},
            },
            "top_performers": [
                {"ticker": "PRIO3", "change_pct": 8.2, "driver": "Recorde de produção"},
                {"ticker": "ENGI11", "change_pct": 3.5, "driver": "Reajuste tarifário"},
            ],
            "bottom_performers": [
                {"ticker": "RAIZ4", "change_pct": -4.8, "driver": "Margem de açúcar comprimida"},
                {"ticker": "PETR4", "change_pct": -1.2, "driver": "Redução de preços de combustíveis"},
            ],
            "key_events": [
                "Redução de 2% no diesel pela Petrobras",
                "Aprovação de usina eólica offshore no RN",
                "Leilão de transmissão com ágio de 35%",
            ],
            "outlook": "neutro_positivo",
        },
        expected_parsed_output={
            "sector": "energy",
            "index_change": 1.8,
            "top_count": 2,
            "bottom_count": 2,
            "outlook": "neutro_positivo",
        },
    ),
    AITestVector(
        scenario="risk_assessment",
        expected_input_pattern="Prepare relatorio de risco para {portfolio_id}",
        mock_response={
            "portfolio_id": "pf-tech",
            "assessment_timestamp": "2026-07-21T14:30:00Z",
            "var_95_daily": 0.038,
            "var_95_monthly": 0.175,
            "expected_shortfall": 0.052,
            "volatility_annualized": 0.247,
            "beta_vs_ibov": 1.32,
            "risk_factors": [
                {
                    "factor": "Concentração em tecnologia",
                    "contribution_pct": 0.42,
                    "mitigation": "Diversificação parcial via ETFs",
                },
                {
                    "factor": "Exposição a juros",
                    "contribution_pct": 0.28,
                    "mitigation": "Duration curta nos ativos de caixa",
                },
                {
                    "factor": "Risco cambial (MELI34)",
                    "contribution_pct": 0.18,
                    "mitigation": "NDF contratado para 70% da exposição",
                },
                {
                    "factor": "Risco de liquidez",
                    "contribution_pct": 0.12,
                    "mitigation": "Posições em ativos com volume médio diário > R$ 50M",
                },
            ],
            "stress_test_results": [
                {
                    "scenario": "Selic a 15%",
                    "impact_pct": -0.085,
                    "recovery_estimate": "6-9 meses",
                },
                {
                    "scenario": "Brent a US$ 50",
                    "impact_pct": -0.032,
                    "recovery_estimate": "3-6 meses",
                },
                {
                    "scenario": "IPCA acima de 7%",
                    "impact_pct": -0.058,
                    "recovery_estimate": "6-12 meses",
                },
            ],
            "overall_risk_rating": "elevado",
            "recommended_max_position": 0.25,
        },
        expected_parsed_output={
            "portfolio_id": "pf-tech",
            "var_95_daily": 0.038,
            "volatility_annualized": 0.247,
            "beta": 1.32,
            "risk_factors_count": 4,
            "stress_scenarios_count": 3,
            "overall_rating": "elevado",
        },
    ),
]


def load_ai_test_vector(scenario: str) -> AITestVector | None:
    for v in AI_TEST_VECTORS:
        if v.scenario == scenario:
            return v
    return None


def ai_scenario_names() -> list[str]:
    return [v.scenario for v in AI_TEST_VECTORS]
