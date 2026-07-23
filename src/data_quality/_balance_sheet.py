from __future__ import annotations

from typing import Any, Literal

from ._models import ValidationResult, _close, _get, _make


def _check_non_negative(
    name: str,
    value: float,
    entity_type: str,
    entity_id: str,
    severity: Literal["error", "warning", "info"] | None = None,
) -> ValidationResult:
    return _make(
        f"{name}_non_negative",
        value >= 0,
        entity_type,
        entity_id,
        severity=(severity if severity is not None else ("error" if value < 0 else "info")),
        **{name: value},
    )


def validate_balance_sheet(line_items: dict[str, Any]) -> list[ValidationResult]:
    entity_type = "balance_sheet"
    entity_id = str(line_items.get("entity_id", ""))
    results: list[ValidationResult] = []
    required = (
        "total_assets",
        "total_liabilities",
        "equity",
        "current_assets",
        "non_current_assets",
        "cash",
        "accounts_receivable",
        "inventory",
    )
    missing = [key for key in required if line_items.get(key) is None]
    if missing:
        return [
            _make(
                "balance_sheet_required_fields",
                False,
                entity_type,
                entity_id,
                severity="error",
                missing_fields=missing,
            )
        ]

    total_assets = _get(line_items, "total_assets")
    total_liabilities = _get(line_items, "total_liabilities")
    equity = _get(line_items, "equity")

    results.append(
        _make(
            "balance_sheet_balances",
            _close(total_assets, total_liabilities + equity),
            entity_type,
            entity_id,
            severity="error",
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            equity=equity,
            difference=total_assets - (total_liabilities + equity),
        )
    )

    for field in ["current_assets", "non_current_assets", "cash", "accounts_receivable", "inventory"]:
        results.append(_check_non_negative(field, _get(line_items, field), entity_type, entity_id))

    results.append(_check_non_negative("total_liabilities", total_liabilities, entity_type, entity_id))
    results.append(_check_non_negative("equity", equity, entity_type, entity_id, severity="warning"))

    return results
