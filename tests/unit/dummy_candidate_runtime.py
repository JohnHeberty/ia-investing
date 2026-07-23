"""Dummy candidate runtime factory for bootstrap integration tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

from ia_investing.orchestration.activities.candidate_intelligence import (
    CallbackCandidateActivityRuntime,
)


async def create_mock_runtime(*_args: object, **_kwargs: object) -> CallbackCandidateActivityRuntime:
    return CallbackCandidateActivityRuntime(
        resolve_identity=AsyncMock(),
        discover_sources=AsyncMock(),
        persist_sources=AsyncMock(),
        validate_supplied_source=AsyncMock(),
        evaluate_readiness=AsyncMock(),
        validate_sources=AsyncMock(),
        collect_documents=AsyncMock(),
        validate_financials=AsyncMock(),
        analyze_fundamentals=AsyncMock(),
        analyze_risk=AsyncMock(),
        build_committee_pack=AsyncMock(),
        complete_run=AsyncMock(),
        screen_universe=AsyncMock(),
        explore_shortlist=AsyncMock(),
        persist_suggestions=AsyncMock(),
    )
