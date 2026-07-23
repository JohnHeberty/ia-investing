from __future__ import annotations

from typing import Any

from ._balance_sheet import validate_balance_sheet
from ._cash_flow import validate_cash_flow
from ._dre import validate_dre
from ._models import ValidationResult

__all__ = [
    "ValidationResult",
    "run_all_checks",
    "validate_balance_sheet",
    "validate_cash_flow",
    "validate_dre",
]

REQUIRED_FIELDS = {
    "BALANCE_SHEET": [
        "total_assets",
        "total_liabilities",
        "equity",
        "current_assets",
        "non_current_assets",
        "cash",
        "accounts_receivable",
        "inventory",
    ],
    "DRE": [
        "receita_liquida",
        "custo_receita",
        "despesas_operacionais",
        "ebitda",
        "ebit",
        "despesas_financeiras",
        "impostos",
        "lucro_liquido",
    ],
    "CASH_FLOW": ["operating_cash_flow", "capital_expenditure", "free_cash_flow", "net_income"],
}


def run_all_checks(statement_type: str, line_items: dict[str, Any]) -> list[ValidationResult]:
    dispatch = {
        "BALANCE_SHEET": validate_balance_sheet,
        "DRE": validate_dre,
        "CASH_FLOW": validate_cash_flow,
    }

    handler = dispatch.get(statement_type)
    if handler is None:
        return [
            ValidationResult(
                check_name="unknown_statement_type",
                passed=False,
                entity_type=statement_type,
                entity_id=str(line_items.get("entity_id", "")),
                details={"statement_type": statement_type},
                severity="error",
            )
        ]

    from ._completeness import check_data_completeness

    completeness = check_data_completeness(statement_type, line_items, REQUIRED_FIELDS[statement_type])
    if not completeness[0].passed:
        return completeness + handler(line_items)
    return handler(line_items)
