from __future__ import annotations

from typing import Any
from uuid import NAMESPACE_URL, uuid5

from temporalio import activity

from metrics import calculate_all


def _mock_run_id(kind: str, identifier: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"ia-investing/mock/{kind}/{identifier}"))


@activity.defn(name="calculate_financial_metrics")
def calculate_financial_metrics(
    issuer_id: str,
    line_items: dict[str, float | int | None],
    statement_type: str,
) -> dict[str, dict[str, float | None]]:
    del issuer_id, statement_type
    return calculate_all(line_items, {})


@activity.defn(name="run_filing_analyst")
def run_filing_analyst(
    issuer_id: str,
    issuer_name: str,
    line_items: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    del issuer_name, line_items, metrics
    return {
        "agent_run_id": _mock_run_id("filing", issuer_id),
        "verdict": "neutral",
        "confidence": 0.5,
        "thesis_effect": "no_change",
        "materiality_score": 0.0,
        "key_claims": [],
        "risks": [],
        "critic_notes": "Deterministic phase-1 mock output.",
    }


@activity.defn(name="run_critic_agent")
def run_critic_agent(
    analyst_output: dict[str, Any],
    line_items: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    del line_items, metrics
    required = {
        "verdict",
        "confidence",
        "thesis_effect",
        "materiality_score",
        "key_claims",
        "risks",
        "critic_notes",
    }
    missing = required - analyst_output.keys()
    if missing:
        raise ValueError(f"mock analyst output missing fields: {sorted(missing)}")
    return {field: analyst_output[field] for field in required}


@activity.defn(name="update_investment_thesis")
def update_investment_thesis(issuer_id: str, assessment: dict[str, Any]) -> dict[str, Any]:
    return {"issuer_id": issuer_id, "assessment": assessment, "persisted": False}


@activity.defn(name="run_news_analyst")
def run_news_analyst(news_item_id: str, title: str, body: str, url: str) -> dict[str, Any]:
    del title, body, url
    return {
        "agent_run_id": _mock_run_id("news", news_item_id),
        "event_type": "unknown",
        "description": "Deterministic phase-1 mock output.",
        "materiality_score": 0.0,
        "direction_hint": "neutral",
        "affected_issuers": [],
    }


@activity.defn(name="compare_with_active_theses")
def compare_with_active_theses(analyst_output: dict[str, Any], issuer_ids: list[str]) -> list[dict[str, Any]]:
    del analyst_output
    return [{"issuer_id": issuer_id, "thesis_effect": "no_change"} for issuer_id in issuer_ids]


@activity.defn(name="update_event_log")
def update_event_log(news_item_id: str, analysis: dict[str, Any]) -> dict[str, Any]:
    return {"news_item_id": news_item_id, "analysis": analysis, "persisted": False}


@activity.defn(name="fetch_b3_universe")
def fetch_b3_universe() -> list[dict[str, Any]]:
    return []


@activity.defn(name="apply_screen_filters")
def apply_screen_filters(universe: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    minimum = float(filters["min_market_cap"])
    maximum = float(filters["max_market_cap"])
    return [item for item in universe if minimum <= float(item["market_cap"]) <= maximum]


@activity.defn(name="calculate_screening_metrics")
def calculate_screening_metrics(filtered: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**item, "screening_score": float(item.get("screening_score", 0.0))} for item in filtered]


@activity.defn(name="identify_anomalies")
def identify_anomalies(scored: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {str(item["issuer_id"]): [] for item in scored}


@activity.defn(name="generate_discovery_briefs")
def generate_discovery_briefs(
    scored: list[dict[str, Any]],
    anomalies: dict[str, list[str]],
) -> list[dict[str, Any]]:
    return [
        {**item, "anomaly_flags": anomalies[str(item["issuer_id"])], "metrics": item.get("metrics", {})}
        for item in scored
    ]


RESEARCH_MOCK_ACTIVITIES = (
    calculate_financial_metrics,
    run_filing_analyst,
    run_critic_agent,
    update_investment_thesis,
    run_news_analyst,
    compare_with_active_theses,
    update_event_log,
    fetch_b3_universe,
    apply_screen_filters,
    calculate_screening_metrics,
    identify_anomalies,
    generate_discovery_briefs,
)
