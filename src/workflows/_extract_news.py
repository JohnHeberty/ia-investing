"""Temporal workflow for news extraction and impact classification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ia_investing.orchestration.policies import EXTERNAL_IO_RETRY_POLICY
    from workflows._schedule_run import complete_schedule_run, fail_schedule_run, start_schedule_run


@dataclass(frozen=True, slots=True)
class ExtractNewsInput:
    issuer_id: str
    max_results: int = 20
    analyze_limit: int = 10
    organization_id: str = ""
    schedule_id: str = ""


@workflow.defn(name="ExtractNewsWorkflow")
class ExtractNewsWorkflow:
    @workflow.run
    async def run(self, command: ExtractNewsInput) -> dict[str, Any]:
        await start_schedule_run(command.schedule_id)
        try:
            result = await self._extract(command)
        except Exception as exc:
            await fail_schedule_run(command.schedule_id, exc)
            raise
        await complete_schedule_run(command.schedule_id, result)
        return result

    async def _extract(self, command: ExtractNewsInput) -> dict[str, Any]:
        fetched: list[dict[str, Any]] = await workflow.execute_activity(
            "fetch_news_items",
            {"issuer_id": command.issuer_id, "max_results": command.max_results},
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=EXTERNAL_IO_RETRY_POLICY,
        )

        analysis: dict[str, Any] = await workflow.execute_activity(
            "batch_analyze_news",
            {"issuer_id": command.issuer_id, "limit": command.analyze_limit},
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=EXTERNAL_IO_RETRY_POLICY,
        )

        fetched_count = 0
        if isinstance(fetched, dict):
            fetched_count = len(fetched.get("items", []))
        elif isinstance(fetched, list):
            fetched_count = len(fetched)

        result = {
            "issuer_id": command.issuer_id,
            "fetched_count": fetched_count,
            "analyzed_count": analysis.get("analyzed", 0) if isinstance(analysis, dict) else 0,
            "results": analysis.get("results", []) if isinstance(analysis, dict) else [],
        }

        return result
