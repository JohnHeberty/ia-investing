from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Literal

from temporalio import workflow


@dataclass(slots=True)
class FilingData:
    issuer_id: str
    issuer_name: str
    statement_type: str
    reporting_period_end: str
    line_items: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FilingReviewVerdict:
    issuer_id: str
    verdict: Literal["positive", "negative", "neutral"]
    confidence: float
    thesis_effect: Literal["strengthen", "weaken", "no_change"]
    materiality_score: float
    key_claims: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    agent_run_id: str = ""
    critic_notes: str = ""


@workflow.defn
class AnalyzeFilingWorkflow:

    @workflow.run
    async def run(self, filing: FilingData) -> FilingReviewVerdict:
        metrics = await workflow.execute_activity(
            "calculate_financial_metrics",
            args=[filing.issuer_id, filing.line_items, filing.statement_type],
            start_to_close_timeout=timedelta(seconds=60),
        )

        analyst_output = await workflow.execute_activity(
            "run_filing_analyst",
            args=[filing.issuer_id, filing.issuer_name, filing.line_items, metrics],
            start_to_close_timeout=timedelta(seconds=120),
        )

        critic_output = await workflow.execute_activity(
            "run_critic_agent",
            args=[analyst_output, filing.line_items, metrics],
            start_to_close_timeout=timedelta(seconds=120),
        )

        verdict = FilingReviewVerdict(
            issuer_id=filing.issuer_id,
            verdict=critic_output.get("verdict", "neutral"),
            confidence=critic_output.get("confidence", 0.0),
            thesis_effect=critic_output.get("thesis_effect", "no_change"),
            materiality_score=critic_output.get("materiality_score", 0.0),
            key_claims=critic_output.get("key_claims", []),
            risks=critic_output.get("risks", []),
            agent_run_id=analyst_output.get("agent_run_id", ""),
            critic_notes=critic_output.get("critic_notes", ""),
        )

        await workflow.execute_activity(
            "update_investment_thesis",
            args=[filing.issuer_id, {
                "verdict": verdict.verdict,
                "confidence": verdict.confidence,
                "thesis_effect": verdict.thesis_effect,
                "materiality_score": verdict.materiality_score,
            }],
            start_to_close_timeout=timedelta(seconds=30),
        )

        await workflow.execute_activity(
            "publish_event",
            args=[
                "filing.analyzed",
                {
                    "issuer_id": filing.issuer_id,
                    "verdict": verdict.verdict,
                    "confidence": verdict.confidence,
                    "thesis_effect": verdict.thesis_effect,
                },
            ],
            start_to_close_timeout=timedelta(seconds=10),
        )

        return verdict
