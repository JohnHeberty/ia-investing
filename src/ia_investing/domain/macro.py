from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class MacroValueRevision:
    effective_date: date
    revision: int
    value: Decimal | None
    value_status: str
    published_at: datetime
    knowledge_at: datetime


@dataclass(frozen=True, slots=True)
class TransformedMacroValue:
    effective_date: date
    value: Decimal | None
    value_status: str
    source_revision: int


def macro_definition_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def validate_macro_definition(*, unit: str, frequency: str, transformation: dict[str, object]) -> None:
    if not unit.strip():
        raise ValueError("macro series unit is required")
    if frequency not in {"daily", "weekly", "monthly", "quarterly", "annual", "irregular"}:
        raise ValueError("unsupported macro series frequency")
    method = str(transformation.get("method", "level"))
    if method not in {"level", "difference", "pct_change", "yoy"}:
        raise ValueError("unsupported macro transformation")
    resample_frequency = transformation.get("resample_frequency")
    if resample_frequency is not None and resample_frequency not in {"monthly", "quarterly", "annual"}:
        raise ValueError("unsupported resampling frequency")
    if transformation.get("aggregation", "last") not in {"last", "sum", "mean"}:
        raise ValueError("unsupported resampling aggregation")


def validate_macro_revision(revision: MacroValueRevision) -> None:
    if revision.revision < 1:
        raise ValueError("macro revision must be positive")
    if revision.knowledge_at.tzinfo is None or revision.published_at.tzinfo is None:
        raise ValueError("macro timestamps must be timezone-aware")
    if revision.knowledge_at < revision.published_at:
        raise ValueError("knowledge_at cannot precede publication")
    if revision.value_status not in {"reported", "missing", "suppressed", "parse_error"}:
        raise ValueError("invalid macro value status")
    if (revision.value_status == "reported") != (revision.value is not None):
        raise ValueError("reported status must match value presence")


def point_in_time_macro_values(
    revisions: tuple[MacroValueRevision, ...], cutoff: datetime
) -> tuple[MacroValueRevision, ...]:
    if cutoff.tzinfo is None:
        raise ValueError("macro cutoff must be timezone-aware")
    selected: dict[date, MacroValueRevision] = {}
    for revision in revisions:
        validate_macro_revision(revision)
        if revision.knowledge_at > cutoff:
            continue
        previous = selected.get(revision.effective_date)
        if previous is None or (revision.revision, revision.knowledge_at) > (
            previous.revision,
            previous.knowledge_at,
        ):
            selected[revision.effective_date] = revision
    return tuple(selected[item] for item in sorted(selected))


def transform_macro_values(revisions: tuple[MacroValueRevision, ...], method: str) -> tuple[TransformedMacroValue, ...]:
    if method not in {"level", "difference", "pct_change", "yoy"}:
        raise ValueError("unsupported macro transformation")
    lag = 12 if method == "yoy" else 1
    output: list[TransformedMacroValue] = []
    for index, current in enumerate(revisions):
        if current.value_status != "reported" or current.value is None:
            output.append(TransformedMacroValue(current.effective_date, None, current.value_status, current.revision))
            continue
        if method == "level":
            value = current.value
        elif index < lag:
            output.append(TransformedMacroValue(current.effective_date, None, "missing", current.revision))
            continue
        else:
            previous = revisions[index - lag]
            if previous.value_status != "reported" or previous.value is None:
                output.append(TransformedMacroValue(current.effective_date, None, "missing", current.revision))
                continue
            if method in {"pct_change", "yoy"}:
                if previous.value == 0:
                    output.append(TransformedMacroValue(current.effective_date, None, "parse_error", current.revision))
                    continue
                value = current.value / previous.value - Decimal(1)
            else:
                value = current.value - previous.value
        output.append(TransformedMacroValue(current.effective_date, value, "reported", current.revision))
    return tuple(output)


def resample_macro_values(
    values: tuple[TransformedMacroValue, ...], *, frequency: str, aggregation: str
) -> tuple[TransformedMacroValue, ...]:
    if frequency not in {"monthly", "quarterly", "annual"}:
        raise ValueError("unsupported resampling frequency")
    if aggregation not in {"last", "sum", "mean"}:
        raise ValueError("unsupported resampling aggregation")
    groups: dict[date, list[TransformedMacroValue]] = {}
    for item in values:
        if frequency == "monthly":
            period = date(item.effective_date.year, item.effective_date.month, 1)
        elif frequency == "quarterly":
            month = ((item.effective_date.month - 1) // 3) * 3 + 1
            period = date(item.effective_date.year, month, 1)
        else:
            period = date(item.effective_date.year, 1, 1)
        groups.setdefault(period, []).append(item)
    output: list[TransformedMacroValue] = []
    for period, members in sorted(groups.items()):
        invalid = next((item for item in members if item.value_status != "reported"), None)
        source_revision = max(item.source_revision for item in members)
        if invalid is not None:
            output.append(TransformedMacroValue(period, None, invalid.value_status, source_revision))
            continue
        reported = [item.value for item in members if item.value is not None]
        if aggregation == "last":
            result = reported[-1]
        elif aggregation == "sum":
            result = sum(reported, start=Decimal(0))
        else:
            result = sum(reported, start=Decimal(0)) / Decimal(len(reported))
        output.append(TransformedMacroValue(period, result, "reported", source_revision))
    return tuple(output)
