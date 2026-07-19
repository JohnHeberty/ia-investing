from __future__ import annotations

from ._accounting import ValidationResult


def check_data_completeness(
    entity_type: str,
    data: dict,
    required_fields: list[str],
) -> list[ValidationResult]:
    missing = [f for f in required_fields if f not in data or data[f] is None]
    entity_id = str(data.get("entity_id", ""))
    total = len(required_fields)
    filled = total - len(missing)

    results: list[ValidationResult] = []

    results.append(ValidationResult(
        check_name="completeness_overall",
        passed=len(missing) == 0,
        entity_type=entity_type,
        entity_id=entity_id,
        details={
            "total_required": total,
            "fields_filled": filled,
            "missing_fields": missing,
            "completeness_pct": round(filled / total * 100, 2) if total else 100.0,
        },
        severity="error" if missing else "info",
    ))

    for field_name in missing:
        results.append(ValidationResult(
            check_name=f"missing_field_{field_name}",
            passed=False,
            entity_type=entity_type,
            entity_id=entity_id,
            details={"field": field_name},
            severity="warning",
        ))

    return results



