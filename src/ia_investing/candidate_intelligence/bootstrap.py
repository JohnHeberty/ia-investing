from __future__ import annotations

import importlib
import inspect
import os
from collections.abc import Callable
from typing import cast

from ia_investing.orchestration.activities.candidate_intelligence import (
    CandidateActivityRuntime,
    candidate_activity_runtime_configured,
    configure_candidate_activity_runtime,
)

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def candidate_intelligence_enabled() -> bool:
    return os.getenv("CANDIDATE_INTELLIGENCE_ENABLED", "false").strip().lower() in _TRUE_VALUES


def _load_factory(path: str) -> Callable[[], object]:
    module_name, separator, attribute = path.partition(":")
    if not separator or not module_name or not attribute:
        raise RuntimeError("CANDIDATE_RUNTIME_FACTORY must use the format 'python.module:factory_name'")
    module = importlib.import_module(module_name)
    factory = getattr(module, attribute, None)
    if factory is None or not callable(factory):
        raise RuntimeError(f"candidate runtime factory is not callable: {path}")
    return cast(Callable[[], object], factory)


async def configure_candidate_runtime_from_environment() -> bool:
    """Configure the candidate runtime exactly once when the feature is enabled.

    The factory may be synchronous or asynchronous and must return an object that
    implements CandidateActivityRuntime. Missing configuration fails worker startup
    instead of allowing workflows to fail later after accepting durable commands.
    """

    if not candidate_intelligence_enabled():
        return False
    if candidate_activity_runtime_configured():
        return True
    factory_path = os.getenv("CANDIDATE_RUNTIME_FACTORY", "").strip()
    if not factory_path:
        raise RuntimeError("candidate intelligence is enabled but CANDIDATE_RUNTIME_FACTORY is not configured")
    result = _load_factory(factory_path)()
    if inspect.isawaitable(result):
        result = await result
    required_methods = (
        "resolve_candidate_identity",
        "discover_candidate_sources",
        "persist_candidate_sources_and_gaps",
        "validate_supplied_candidate_source",
        "evaluate_candidate_readiness",
        "validate_candidate_sources",
        "collect_candidate_documents",
        "validate_candidate_financial_data",
        "run_candidate_fundamental_analysis",
        "run_candidate_risk_analysis",
        "create_committee_pack",
        "complete_candidate_analysis_run",
        "screen_equity_universe",
        "run_equity_explorer_agent",
        "persist_exploration_suggestions",
    )
    missing = [name for name in required_methods if not callable(getattr(result, name, None))]
    if missing:
        raise RuntimeError("candidate runtime factory returned an incompatible object; missing: " + ", ".join(missing))
    configure_candidate_activity_runtime(cast(CandidateActivityRuntime, result))
    return True
