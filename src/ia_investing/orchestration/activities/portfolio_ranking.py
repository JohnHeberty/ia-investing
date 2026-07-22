"""Materialize validated, deterministic portfolio ranking snapshots."""

from __future__ import annotations

from typing import Any

from temporalio import activity
from temporalio.exceptions import ApplicationError

from ia_investing.application.portfolio_ranking_materializer import (
    PortfolioRankingMaterializer,
    RankingEvidenceBundle,
)
from ia_investing.platform.database import DatabaseRuntime
from ia_investing.settings import get_settings


@activity.defn(name="persist_portfolio_ranking_snapshot")
async def persist_portfolio_ranking_snapshot(payload: dict[str, Any]) -> str:
    try:
        bundle = RankingEvidenceBundle.model_validate(payload)
    except Exception as exc:
        raise ApplicationError(
            "invalid portfolio ranking evidence bundle",
            type="DataValidationError",
            non_retryable=True,
        ) from exc

    runtime = DatabaseRuntime.create(get_settings().database.url)
    try:
        async with runtime.session() as session:
            snapshot_id = await PortfolioRankingMaterializer(session).persist(bundle)
            await session.commit()
            return str(snapshot_id)
    finally:
        await runtime.dispose()


PORTFOLIO_RANKING_ACTIVITIES = (persist_portfolio_ranking_snapshot,)
