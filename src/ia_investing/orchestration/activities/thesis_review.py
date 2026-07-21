from __future__ import annotations

from typing import Any

from temporalio import activity

from ia_investing.orchestration.activities._telemetry import activity_span


@activity.defn(name="load_thesis_context")
def load_thesis_context(thesis_id: str, data_as_of: str, knowledge_cutoff: str) -> dict[str, Any]:
    with activity_span("load_thesis_context"):
        return {
            "thesis_id": thesis_id,
            "data_as_of": data_as_of,
            "knowledge_cutoff": knowledge_cutoff,
            "content_sha256": "mock_sha256_placeholder",
            "status": "active",
            "summary": "Mock thesis context for review",
            "assumptions": [],
            "catalysts": [],
            "risks": [],
            "recommendation": "hold",
        }


@activity.defn(name="run_specialist_filing")
def run_specialist_filing(
    issuer_id: str,
    thesis_context: dict[str, Any],
    data_as_of: str,
    knowledge_cutoff: str,
) -> dict[str, Any]:
    with activity_span("run_specialist_filing"):
        del issuer_id, thesis_context, data_as_of, knowledge_cutoff
        return {
            "verdict": "neutral",
            "confidence": 0.7,
            "thesis_effect": "no_change",
            "key_claims": [],
            "risks": [],
            "contradictions": [],
        }


@activity.defn(name="run_specialist_news")
def run_specialist_news(
    issuer_id: str,
    thesis_context: dict[str, Any],
    data_as_of: str,
    knowledge_cutoff: str,
) -> dict[str, Any]:
    with activity_span("run_specialist_news"):
        del issuer_id, thesis_context, data_as_of, knowledge_cutoff
        return {
            "verdict": "neutral",
            "confidence": 0.6,
            "thesis_effect": "no_change",
            "key_claims": [],
            "risks": [],
            "contradictions": [],
        }


@activity.defn(name="run_specialist_macro")
def run_specialist_macro(
    issuer_id: str,
    thesis_context: dict[str, Any],
    data_as_of: str,
    knowledge_cutoff: str,
) -> dict[str, Any]:
    with activity_span("run_specialist_macro"):
        del issuer_id, thesis_context, data_as_of, knowledge_cutoff
        return {
            "verdict": "neutral",
            "confidence": 0.5,
            "thesis_effect": "no_change",
            "key_claims": [],
            "risks": [],
            "contradictions": [],
        }


@activity.defn(name="run_specialist_political")
def run_specialist_political(
    issuer_id: str,
    thesis_context: dict[str, Any],
    data_as_of: str,
    knowledge_cutoff: str,
) -> dict[str, Any]:
    with activity_span("run_specialist_political"):
        del issuer_id, thesis_context, data_as_of, knowledge_cutoff
        return {
            "verdict": "neutral",
            "confidence": 0.4,
            "thesis_effect": "no_change",
            "key_claims": [],
            "risks": [],
            "contradictions": [],
        }


@activity.defn(name="run_specialist_critic")
def run_specialist_critic(
    issuer_id: str,
    thesis_context: dict[str, Any],
    data_as_of: str,
    knowledge_cutoff: str,
) -> dict[str, Any]:
    with activity_span("run_specialist_critic"):
        del issuer_id, thesis_context, data_as_of, knowledge_cutoff
        return {
            "verdict": "neutral",
            "confidence": 0.6,
            "thesis_effect": "no_change",
            "key_claims": [],
            "risks": [],
            "contradictions": [],
        }


THESIS_REVIEW_ACTIVITIES = (
    load_thesis_context,
    run_specialist_filing,
    run_specialist_news,
    run_specialist_macro,
    run_specialist_political,
    run_specialist_critic,
)
