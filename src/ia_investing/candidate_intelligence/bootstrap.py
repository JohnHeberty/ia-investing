from __future__ import annotations

import importlib
import inspect
from typing import Any

from ia_investing.orchestration.activities.candidate_intelligence import (
    candidate_activity_runtime_configured,
    configure_candidate_activity_runtime,
)
from ia_investing.platform.database.runtime import DatabaseRuntime
from ia_investing.settings import get_settings


def candidate_intelligence_enabled() -> bool:
    return get_settings().candidate.enabled


def _load_factory(path: str) -> Any:
    module_name, separator, attribute = path.partition(":")
    if not separator or not module_name or not attribute:
        raise RuntimeError("candidate.runtime_factory must use the format 'python.module:factory_name'")
    module = importlib.import_module(module_name)
    factory = getattr(module, attribute, None)
    if factory is None or not callable(factory):
        raise RuntimeError(f"candidate runtime factory is not callable: {path}")
    return factory


async def configure_candidate_runtime_from_environment(
    db: DatabaseRuntime | None = None,
) -> bool:
    """Configure the candidate runtime exactly once when the feature is enabled.

    The factory receives the shared DatabaseRuntime as its single argument so that
    connection-pool lifecycle is managed by the caller (the worker or API process).

    The factory may be synchronous or asynchronous and must return an object that
    implements CandidateActivityRuntime.
    """

    if not candidate_intelligence_enabled():
        return False
    if candidate_activity_runtime_configured():
        return True
    settings = get_settings()
    factory_path = settings.candidate.runtime_factory

    if db is None:
        db = DatabaseRuntime.create(get_settings().database.url)

    factory = _load_factory(factory_path)
    result = factory(db)
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
    configure_candidate_activity_runtime(result)
    return True
