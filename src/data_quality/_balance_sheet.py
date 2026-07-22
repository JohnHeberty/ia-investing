from __future__ import annotations

from ._models import ValidationResult, _close, _get, _make


def validate_balance_sheet(line_items: dict) -> list[ValidationResult]:
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

    current_assets = _get(line_items, "current_assets")
    results.append(
        _make(
            "current_assets_non_negative",
            current_assets >= 0,
            entity_type,
            entity_id,
            severity="error" if current_assets < 0 else "info",
            current_assets=current_assets,
        )
    )

    non_current_assets = _get(line_items, "non_current_assets")
    results.append(
        _make(
            "non_current_assets_non_negative",
            non_current_assets >= 0,
            entity_type,
            entity_id,
            severity="error" if non_current_assets < 0 else "info",
            non_current_assets=non_current_assets,
        )
    )

    results.append(
        _make(
            "total_liabilities_non_negative",
            total_liabilities >= 0,
            entity_type,
            entity_id,
            severity="error" if total_liabilities < 0 else "info",
            total_liabilities=total_liabilities,
        )
    )

    results.append(
        _make(
            "equity_non_negative",
            equity >= 0,
            entity_type,
            entity_id,
            severity="warning" if equity < 0 else "info",
            equity=equity,
        )
    )

    cash = _get(line_items, "cash")
    results.append(
        _make(
            "cash_non_negative",
            cash >= 0,
            entity_type,
            entity_id,
            severity="error" if cash < 0 else "info",
            cash=cash,
        )
    )

    accounts_receivable = _get(line_items, "accounts_receivable")
    results.append(
        _make(
            "accounts_receivable_non_negative",
            accounts_receivable >= 0,
            entity_type,
            entity_id,
            severity="error" if accounts_receivable < 0 else "info",
            accounts_receivable=accounts_receivable,
        )
    )

    inventory = _get(line_items, "inventory")
    results.append(
        _make(
            "inventory_non_negative",
            inventory >= 0,
            entity_type,
            entity_id,
            severity="error" if inventory < 0 else "info",
            inventory=inventory,
        )
    )

    return results
