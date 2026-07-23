from __future__ import annotations

from typing import Any

from ._models import ValidationResult, _close, _get, _make


def validate_cash_flow(line_items: dict[str, Any]) -> list[ValidationResult]:
    entity_type = "cash_flow"
    entity_id = str(line_items.get("entity_id", ""))
    results: list[ValidationResult] = []
    required = ("operating_cash_flow", "capital_expenditure", "free_cash_flow", "net_income")
    missing = [key for key in required if line_items.get(key) is None]
    if missing:
        return [
            _make(
                "cash_flow_required_fields",
                False,
                entity_type,
                entity_id,
                severity="error",
                missing_fields=missing,
            )
        ]

    operating_cf = _get(line_items, "operating_cash_flow")
    capex = _get(line_items, "capital_expenditure")
    free_cf = _get(line_items, "free_cash_flow")
    net_income = _get(line_items, "net_income")

    ratio: float | None = None
    if net_income != 0:
        ratio = operating_cf / net_income
        reasonable = -10.0 <= ratio <= 10.0
    else:
        reasonable = abs(operating_cf) < 1.0

    results.append(
        _make(
            "operating_cf_vs_net_income",
            reasonable,
            entity_type,
            entity_id,
            severity="warning",
            operating_cash_flow=operating_cf,
            net_income=net_income,
            ratio=ratio,
        )
    )

    results.append(
        _make(
            "capex_sign_consistency",
            capex <= 0,
            entity_type,
            entity_id,
            severity="warning",
            capital_expenditure=capex,
        )
    )

    expected_fcf = operating_cf - capex
    results.append(
        _make(
            "free_cash_flow_consistency",
            _close(free_cf, expected_fcf),
            entity_type,
            entity_id,
            severity="warning",
            free_cash_flow=free_cf,
            expected_free_cash_flow=expected_fcf,
            difference=free_cf - expected_fcf,
        )
    )

    return results
