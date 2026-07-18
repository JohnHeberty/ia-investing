from __future__ import annotations

from ._balance_sheet import validate_balance_sheet
from ._cash_flow import validate_cash_flow
from ._dre import validate_dre
from ._models import ValidationResult


def run_all_checks(statement_type: str, line_items: dict) -> list[ValidationResult]:
    dispatch = {
        "BALANCE_SHEET": validate_balance_sheet,
        "DRE": validate_dre,
        "CASH_FLOW": validate_cash_flow,
    }

    handler = dispatch.get(statement_type)
    if handler is None:
        return [ValidationResult(
            check_name="unknown_statement_type",
            passed=False,
            entity_type=statement_type,
            entity_id=str(line_items.get("entity_id", "")),
            details={"statement_type": statement_type},
            severity="error",
        )]

    return handler(line_items)
