from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Literal

from temporalio import workflow


@dataclass(slots=True)
class NewsArticle:
    news_item_id: str
    title: str
    body: str
    url: str
    source_name: str
    published_at: str
    issuer_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class NewsAnalysis:
    news_item_id: str
    event_type: str
    description: str
    materiality_score: float
    direction_hint: Literal["positive", "negative", "neutral"]
    affected_issuers: list[str] = field(default_factory=list)
    thesis_effects: list[dict[str, Any]] = field(default_factory=list)
    agent_run_id: str = ""


@workflow.defn
class AnalyzeNewsWorkflow:

    @workflow.run
    async def run(self, article: NewsArticle) -> NewsAnalysis:
        analyst_output = await workflow.execute_activity(
            "run_news_analyst",
            args=[article.news_item_id, article.title, article.body, article.url],
            start_to_close_timeout=timedelta(seconds=120),
        )

        thesis_comparisons = await workflow.execute_activity(
            "compare_with_active_theses",
            args=[analyst_output, article.issuer_ids],
            start_to_close_timeout=timedelta(seconds=60),
        )

        analysis = NewsAnalysis(
            news_item_id=article.news_item_id,
            event_type=analyst_output.get("event_type", "unknown"),
            description=analyst_output.get("description", ""),
            materiality_score=analyst_output.get("materiality_score", 0.0),
            direction_hint=analyst_output.get("direction_hint", "neutral"),
            affected_issuers=analyst_output.get("affected_issuers", []),
            thesis_effects=thesis_comparisons,
            agent_run_id=analyst_output.get("agent_run_id", ""),
        )

        await workflow.execute_activity(
            "update_event_log",
            args=[article.news_item_id, {
                "event_type": analysis.event_type,
                "description": analysis.description,
                "materiality_score": analysis.materiality_score,
                "direction_hint": analysis.direction_hint,
                "affected_issuers": analysis.affected_issuers,
                "thesis_effects": analysis.thesis_effects,
            }],
            start_to_close_timeout=timedelta(seconds=30),
        )

        await workflow.execute_activity(
            "publish_event",
            args=[
                "news.analyzed",
                {
                    "news_item_id": article.news_item_id,
                    "event_type": analysis.event_type,
                    "materiality_score": analysis.materiality_score,
                    "direction_hint": analysis.direction_hint,
                    "affected_issuers": analysis.affected_issuers,
                },
            ],
            start_to_close_timeout=timedelta(seconds=10),
        )

        return analysis
