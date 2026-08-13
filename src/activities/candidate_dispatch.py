"""Compatibility import for the canonical candidate outbox dispatch activities."""

from ia_investing.orchestration.activities.candidate_dispatch import (  # noqa: F401
    create_scheduled_exploration_run,
    dispatch_candidate_intelligence_events,
)
