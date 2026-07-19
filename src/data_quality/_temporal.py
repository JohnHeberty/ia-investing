from __future__ import annotations

from datetime import date as _date

from ._accounting import ValidationResult


def check_temporal_consistency(
    time_series: list[dict],
    date_field: str,
    value_field: str,
) -> list[ValidationResult]:
    if not time_series:
        return [ValidationResult(
            check_name="temporal_empty_series",
            passed=False,
            entity_type="time_series",
            entity_id="",
            details={"record_count": 0},
            severity="error",
        )]

    entity_id = str(time_series[0].get("entity_id", ""))
    results: list[ValidationResult] = []

    sorted_ok = True
    out_of_order_indices: list[int] = []
    for i in range(1, len(time_series)):
        prev = time_series[i - 1].get(date_field)
        curr = time_series[i].get(date_field)
        if prev is not None and curr is not None and curr < prev:
            sorted_ok = False
            out_of_order_indices.append(i)

    results.append(ValidationResult(
        check_name="temporal_sorted",
        passed=sorted_ok,
        entity_type="time_series",
        entity_id=entity_id,
        details={
            "out_of_order_count": len(out_of_order_indices),
            "out_of_order_indices": out_of_order_indices[:20],
        },
        severity="error" if not sorted_ok else "info",
    ))

    seen_dates: dict[str, int] = {}
    duplicates: list[tuple[int, str]] = []
    for i, record in enumerate(time_series):
        date_val = record.get(date_field)
        if date_val is None:
            continue
        date_key = str(date_val)
        if date_key in seen_dates:
            duplicates.append((i, date_key))
        seen_dates[date_key] = seen_dates.get(date_key, 0) + 1

    has_duplicates = len(duplicates) > 0
    results.append(ValidationResult(
        check_name="temporal_no_duplicates",
        passed=not has_duplicates,
        entity_type="time_series",
        entity_id=entity_id,
        details={
            "duplicate_count": len(duplicates),
            "duplicate_dates": [d for _, d in duplicates[:20]],
        },
        severity="error" if has_duplicates else "info",
    ))

    gaps: list[dict[str, str]] = []
    dates_list = [str(r.get(date_field, "")) for r in time_series if r.get(date_field) is not None]
    dates_list.sort()
    if len(dates_list) >= 2:
        for i in range(1, len(dates_list)):
            prev_str = dates_list[i - 1]
            curr_str = dates_list[i]
            try:
                prev_d = _date.fromisoformat(prev_str) if isinstance(prev_str, str) else prev_str
                curr_d = _date.fromisoformat(curr_str) if isinstance(curr_str, str) else curr_str
                delta = (curr_d - prev_d).days
                if delta > 90:
                    gaps.append({"from": prev_str, "to": curr_str, "gap_days": str(delta)})
            except (ValueError, TypeError):
                pass

    results.append(ValidationResult(
        check_name="temporal_no_large_gaps",
        passed=len(gaps) == 0,
        entity_type="time_series",
        entity_id=entity_id,
        details={"gap_count": len(gaps), "gaps": gaps[:10]},
        severity="warning" if gaps else "info",
    ))

    return results
