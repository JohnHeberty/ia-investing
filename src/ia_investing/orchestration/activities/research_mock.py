from __future__ import annotations

from typing import Any
from uuid import NAMESPACE_URL, uuid5

from temporalio import activity

from ia_investing.contracts.v1 import DiscoveryBriefV1, FilingReviewV1, NewsAnalysisV1
from ia_investing.orchestration.activities._telemetry import activity_span
from metrics import calculate_all


def _mock_run_id(kind: str, identifier: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"ia-investing/mock/{kind}/{identifier}"))


@activity.defn(name="calculate_financial_metrics")
def calculate_financial_metrics(
    issuer_id: str,
    line_items: dict[str, float | int | None],
    statement_type: str,
) -> dict[str, dict[str, float | None]]:
    with activity_span("calculate_financial_metrics"):
        del issuer_id, statement_type
        return calculate_all(line_items, {})


@activity.defn(name="run_filing_analyst")
def run_filing_analyst(
    issuer_id: str,
    issuer_name: str,
    line_items: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    with activity_span("run_filing_analyst"):
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
) -> FilingReviewV1:
    with activity_span("run_critic_agent"):
        del line_items, metrics
        return FilingReviewV1(
            issuer_id=analyst_output.get("issuer_id", ""),
            verdict=analyst_output["verdict"],
            confidence=analyst_output["confidence"],
            thesis_effect=analyst_output["thesis_effect"],
            materiality_score=analyst_output["materiality_score"],
            key_claims=analyst_output["key_claims"],
            risks=analyst_output["risks"],
            agent_run_id=analyst_output["agent_run_id"],
            critic_notes=analyst_output["critic_notes"],
        )


@activity.defn(name="update_investment_thesis")
def update_investment_thesis(issuer_id: str, assessment: dict[str, Any]) -> dict[str, Any]:
    with activity_span("update_investment_thesis"):
        return {"issuer_id": issuer_id, "assessment": assessment, "persisted": False}


@activity.defn(name="run_news_analyst")
def run_news_analyst(news_item_id: str, title: str, body: str, url: str) -> NewsAnalysisV1:
    with activity_span("run_news_analyst"):
        del title, body, url
        return NewsAnalysisV1(
            news_item_id=news_item_id,
            event_type="unknown",
            description="Deterministic phase-1 mock output.",
            materiality_score=0.0,
            direction_hint="neutral",
            affected_issuers=[],
            thesis_effects=[],
            agent_run_id=_mock_run_id("news", news_item_id),
        )


@activity.defn(name="compare_with_active_theses")
def compare_with_active_theses(analyst_output: dict[str, Any], issuer_ids: list[str]) -> list[dict[str, Any]]:
    with activity_span("compare_with_active_theses"):
        del analyst_output
        return [{"issuer_id": issuer_id, "thesis_effect": "no_change"} for issuer_id in issuer_ids]


@activity.defn(name="update_event_log")
def update_event_log(news_item_id: str, analysis: dict[str, Any]) -> dict[str, Any]:
    with activity_span("update_event_log"):
        return {"news_item_id": news_item_id, "analysis": analysis, "persisted": False}


@activity.defn(name="fetch_b3_universe")
def fetch_b3_universe() -> list[dict[str, Any]]:
    with activity_span("fetch_b3_universe"):
        return []


@activity.defn(name="apply_screen_filters")
def apply_screen_filters(universe: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    with activity_span("apply_screen_filters"):
        raw_min = filters.get("min_market_cap")
        raw_max = filters.get("max_market_cap")
        minimum = float(raw_min) if raw_min is not None else 0.0
        maximum = float(raw_max) if raw_max is not None else float("inf")
        return [item for item in universe if minimum <= float(item["market_cap"]) <= maximum]


@activity.defn(name="calculate_screening_metrics")
def calculate_screening_metrics(filtered: list[dict[str, Any]]) -> list[dict[str, Any]]:
    with activity_span("calculate_screening_metrics"):
        result = []
        for item in filtered:
            score = float(item["screening_score"]) if "screening_score" in item else 0.0
            result.append({**item, "screening_score": score})
        return result


@activity.defn(name="identify_anomalies")
def identify_anomalies(scored: list[dict[str, Any]]) -> dict[str, list[str]]:
    with activity_span("identify_anomalies"):
        return {str(item["issuer_id"]): [] for item in scored}


@activity.defn(name="generate_discovery_briefs")
def generate_discovery_briefs(
    scored: list[dict[str, Any]],
    anomalies: dict[str, list[str]],
) -> list[DiscoveryBriefV1]:
    with activity_span("generate_discovery_briefs"):
        return [
            DiscoveryBriefV1(
                issuer_id=str(item["issuer_id"]),
                ticker_symbol=str(item.get("ticker_symbol", "")),
                issuer_name=str(item.get("issuer_name", "")),
                sector=str(item.get("sector", "")),
                market_cap=float(item.get("market_cap", 0.0)),
                screening_score=float(item.get("screening_score", 0.0)),
                anomaly_flags=anomalies.get(str(item["issuer_id"]), []),
                metrics=item.get("metrics", {}),
            )
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
