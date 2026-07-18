from __future__ import annotations

from ._models import ValidationResult, _close, _get, _make


def validate_dre(line_items: dict) -> list[ValidationResult]:
    entity_type = "dre"
    entity_id = str(line_items.get("entity_id", ""))
    results: list[ValidationResult] = []

    receita_liquida = _get(line_items, "receita_liquida")
    custo_receita = _get(line_items, "custo_receita")
    despesas_operacionais = _get(line_items, "despesas_operacionais")
    ebitda = _get(line_items, "ebitda")
    ebit = _get(line_items, "ebit")
    despesas_financeiras = _get(line_items, "despesas_financeiras")
    impostos = _get(line_items, "impostos")
    lucro_liquido = _get(line_items, "lucro_liquido")

    results.append(_make(
        "receita_liquida_non_negative",
        receita_liquida >= 0,
        entity_type,
        entity_id,
        severity="error" if receita_liquida < 0 else "info",
        receita_liquida=receita_liquida,
    ))

    results.append(_make(
        "custo_receita_lte_receita",
        custo_receita <= receita_liquida,
        entity_type,
        entity_id,
        severity="error" if custo_receita > receita_liquida else "info",
        custo_receita=custo_receita,
        receita_liquida=receita_liquida,
    ))

    expected_ebitda = receita_liquida - custo_receita - despesas_operacionais
    results.append(_make(
        "ebitda_consistency",
        _close(ebitda, expected_ebitda),
        entity_type,
        entity_id,
        severity="warning",
        ebitda=ebitda,
        expected_ebitda=expected_ebitda,
        difference=ebitda - expected_ebitda,
    ))

    expected_lucro = ebit - despesas_financeiras - impostos
    results.append(_make(
        "lucro_liquido_consistency",
        _close(lucro_liquido, expected_lucro),
        entity_type,
        entity_id,
        severity="warning",
        lucro_liquido=lucro_liquido,
        expected_lucro=expected_lucro,
        difference=lucro_liquido - expected_lucro,
    ))

    has_negative_revenue = line_items.get("allow_negative_revenue", False)
    if not has_negative_revenue:
        results.append(_make(
            "no_negative_revenue",
            receita_liquida >= 0,
            entity_type,
            entity_id,
            severity="error" if receita_liquida < 0 else "info",
            receita_liquida=receita_liquida,
        ))

    return results
