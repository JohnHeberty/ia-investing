"""Ownership policy for declaratively managed Temporal schedules."""

from __future__ import annotations

MANAGED_SCHEDULE_EXACT_IDS = frozenset({"news-dedup-cleanup", "operation-outbox-dispatch"})
MANAGED_SCHEDULE_PREFIXES = (
    "news-collection-",
    "cvm-dfp-",
    "paper-reconciliation-",
    "paper-valuation-",
    "paper-rebalance-",
)


def is_managed_schedule_id(schedule_id: str) -> bool:
    """Return whether a schedule is owned by the declarative scheduler."""
    return schedule_id in MANAGED_SCHEDULE_EXACT_IDS or schedule_id.startswith(MANAGED_SCHEDULE_PREFIXES)
