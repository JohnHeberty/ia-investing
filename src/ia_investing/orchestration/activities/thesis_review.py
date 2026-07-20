from __future__ import annotations

from typing import Any


def load_thesis_context(
    thesis_id: str, data_as_of: str, knowledge_cutoff: str
) -> dict[str, Any]:
    """Load thesis context for review — mock implementation."""
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


def run_specialist_filing(
    issuer_id: str,
    thesis_context: dict[str, Any],
    data_as_of: str,
    knowledge_cutoff: str,
) -> dict[str, Any]:
    """Mock filing specialist for thesis review."""
    return {
        "verdict": "neutral",
        "confidence": 0.7,
        "thesis_effect": "no_change",
        "key_claims": [],
        "risks": [],
        "contradictions": [],
    }


def run_specialist_news(
    issuer_id: str,
    thesis_context: dict[str, Any],
    data_as_of: str,
    knowledge_cutoff: str,
) -> dict[str, Any]:
    """Mock news specialist for thesis review."""
    return {
        "verdict": "neutral",
        "confidence": 0.6,
        "thesis_effect": "no_change",
        "key_claims": [],
        "risks": [],
        "contradictions": [],
    }


def run_specialist_macro(
    issuer_id: str,
    thesis_context: dict[str, Any],
    data_as_of: str,
    knowledge_cutoff: str,
) -> dict[str, Any]:
    """Mock macro specialist for thesis review."""
    return {
        "verdict": "neutral",
        "confidence": 0.5,
        "thesis_effect": "no_change",
        "key_claims": [],
        "risks": [],
        "contradictions": [],
    }


def run_specialist_political(
    issuer_id: str,
    thesis_context: dict[str, Any],
    data_as_of: str,
    knowledge_cutoff: str,
) -> dict[str, Any]:
    """Mock political specialist for thesis review."""
    return {
        "verdict": "neutral",
        "confidence": 0.4,
        "thesis_effect": "no_change",
        "key_claims": [],
        "risks": [],
        "contradictions": [],
    }


def run_specialist_critic(
    issuer_id: str,
    thesis_context: dict[str, Any],
    data_as_of: str,
    knowledge_cutoff: str,
) -> dict[str, Any]:
    """Mock critic specialist for thesis review."""
    return {
        "verdict": "neutral",
        "confidence": 0.6,
        "thesis_effect": "no_change",
        "key_claims": [],
        "risks": [],
        "contradictions": [],
    }


THESIS_REVIEW_ACTIVITIES = [
    load_thesis_context,
    run_specialist_filing,
    run_specialist_news,
    run_specialist_macro,
    run_specialist_political,
    run_specialist_critic,
]
