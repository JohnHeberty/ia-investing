"""Compute derived financial metrics from canonical line-item dictionaries."""

from __future__ import annotations


def compute_derived_metrics(canonical: dict[str, float]) -> dict[str, float]:
    derived: dict[str, float] = {}

    receita = canonical.get("receita_liquida", 0.0)
    custo = canonical.get("custo_receita", 0.0)
    despesas_op = (
        canonical.get("despesas_vendas", 0.0)
        + canonical.get("despesas_administrativas", 0.0)
        + canonical.get("outras_despesas_operacionais", 0.0)
        - canonical.get("outras_receitas_operacionais", 0.0)
    )

    lucro_bruto = canonical.get("lucro_bruto", 0.0)
    if lucro_bruto == 0.0 and receita != 0.0:
        lucro_bruto = receita - custo
        derived["lucro_bruto"] = lucro_bruto

    ebitda = canonical.get("ebitda", 0.0)
    if ebitda == 0.0:
        da = canonical.get("depreciacao_amortizacao", 0.0)
        ebit = canonical.get("ebit", 0.0)
        if ebit != 0.0:
            ebitda = ebit + da
        elif lucro_bruto != 0.0:
            ebitda = lucro_bruto - despesas_op + da
        if ebitda != 0.0:
            derived["ebitda"] = ebitda

    ebit = canonical.get("ebit", 0.0)
    if ebit == 0.0 and ebitda != 0.0:
        da = canonical.get("depreciacao_amortizacao", 0.0)
        ebit = ebitda - da
        derived["ebit"] = ebit

    total_ativos = canonical.get("total_ativos", 0.0)
    patrimonio = canonical.get("patrimonio_liquido", 0.0)

    lucro_liquido = canonical.get("lucro_liquido", 0.0)

    if receita > 0:
        derived["margem_bruta"] = lucro_bruto / receita
        derived["margem_ebitda"] = ebitda / receita
        derived["margem_liquida"] = lucro_liquido / receita

    if patrimonio > 0:
        derived["roe"] = lucro_liquido / patrimonio

    if total_ativos > 0:
        derived["roa"] = lucro_liquido / total_ativos
        derived["giro_ativo"] = receita / total_ativos

    return derived
