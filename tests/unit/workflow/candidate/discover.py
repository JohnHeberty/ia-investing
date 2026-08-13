"""Unit tests for workflows._discover — DiscoverStocksWorkflow, ScreenFilters, DiscoveryBrief."""

from __future__ import annotations

from typing import Any

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows._discover import DiscoverStocksWorkflow, DiscoveryBrief, ScreenFilters

TASK_QUEUE = "test-discover"


@pytest.mark.unit
class TestScreenFilters:
    def test_defaults(self):
        f = ScreenFilters()
        assert f.min_market_cap == 0.0
        assert f.max_market_cap is None
        assert f.sectors_include == []
        assert f.sectors_exclude == []
        assert f.min_volume_avg == 0.0
        assert f.exclude_penny_stocks is True

    def test_custom_values(self):
        f = ScreenFilters(
            min_market_cap=1e9,
            max_market_cap=1e12,
            sectors_include=["Finance"],
            sectors_exclude=["Mining"],
            min_volume_avg=1e6,
            exclude_penny_stocks=False,
        )
        assert f.min_market_cap == 1e9
        assert f.sectors_include == ["Finance"]

    def test_equality(self):
        a = ScreenFilters(min_market_cap=1e9)
        b = ScreenFilters(min_market_cap=1e9)
        assert a == b

    def test_inequality(self):
        a = ScreenFilters(min_market_cap=1e9)
        b = ScreenFilters(min_market_cap=2e9)
        assert a != b


@pytest.mark.unit
class TestDiscoveryBrief:
    def test_construction(self):
        b = DiscoveryBrief(
            issuer_id="i1",
            ticker_symbol="PETR4",
            issuer_name="Petrobras",
            sector="Oil",
            market_cap=1e12,
            screening_score=0.95,
        )
        assert b.anomaly_flags == []
        assert b.metrics == {}

    def test_with_anomalies(self):
        b = DiscoveryBrief(
            issuer_id="i1",
            ticker_symbol="PETR4",
            issuer_name="Petrobras",
            sector="Oil",
            market_cap=1e12,
            screening_score=0.95,
            anomaly_flags=["high_vol", "low_liquidity"],
            metrics={"pe": 15.0},
        )
        assert len(b.anomaly_flags) == 2


def _make_discover_activities(
    universe: list | None = None,
    filtered: list | None = None,
    scored: list | None = None,
    anomalies: list | None = None,
    briefs: list | None = None,
):
    captured_publish: list[dict[str, Any]] = []

    @activity.defn(name="fetch_b3_universe")
    async def fake_universe() -> list:
        return universe or []

    @activity.defn(name="apply_screen_filters")
    async def fake_filter(universe_arg: list, filters: dict) -> list:
        return filtered if filtered is not None else []

    @activity.defn(name="calculate_screening_metrics")
    async def fake_score(filtered_arg: list) -> list:
        return scored if scored is not None else []

    @activity.defn(name="identify_anomalies")
    async def fake_anomalies(scored_arg: list) -> list:
        return anomalies if anomalies is not None else []

    @activity.defn(name="generate_discovery_briefs")
    async def fake_briefs(scored_arg: list, anomalies_arg: list) -> list:
        return briefs if briefs is not None else []

    @activity.defn(name="publish_event")
    async def fake_publish(topic: str, payload: dict) -> None:
        captured_publish.append({"topic": topic, "payload": payload})

    activities = [fake_universe, fake_filter, fake_score, fake_anomalies, fake_briefs, fake_publish]
    return activities, captured_publish


@pytest.mark.unit
class TestDiscoverStocksWorkflow:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        acts, _publish = _make_discover_activities(
            universe=[{"ticker": "PETR4"}, {"ticker": "VALE3"}],
            filtered=[{"ticker": "PETR4"}, {"ticker": "VALE3"}],
            scored=[{"ticker": "PETR4", "score": 0.9}, {"ticker": "VALE3", "score": 0.8}],
            anomalies=[{"ticker": "PETR4", "anomalies": []}, {"ticker": "VALE3", "anomalies": ["low_vol"]}],
            briefs=[
                {
                    "issuer_id": "i1",
                    "ticker_symbol": "PETR4",
                    "issuer_name": "Petrobras",
                    "sector": "Oil",
                    "market_cap": 1e12,
                    "screening_score": 0.9,
                    "anomaly_flags": [],
                    "metrics": {},
                },
                {
                    "issuer_id": "i2",
                    "ticker_symbol": "VALE3",
                    "issuer_name": "Vale",
                    "sector": "Mining",
                    "market_cap": 5e11,
                    "screening_score": 0.8,
                    "anomaly_flags": ["low_vol"],
                    "metrics": {},
                },
            ],
        )

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[DiscoverStocksWorkflow]):
                result = await env.client.execute_workflow(
                    DiscoverStocksWorkflow.run,
                    ScreenFilters(),
                    id="test-discover-1",
                    task_queue=TASK_QUEUE,
                )

        assert len(result) == 2
        assert result[0].ticker_symbol == "PETR4"
        assert result[1].anomaly_flags == ["low_vol"]

    @pytest.mark.asyncio
    async def test_empty_universe(self):
        acts, _publish = _make_discover_activities()

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[DiscoverStocksWorkflow]):
                result = await env.client.execute_workflow(
                    DiscoverStocksWorkflow.run,
                    ScreenFilters(min_market_cap=1e10),
                    id="test-discover-2",
                    task_queue=TASK_QUEUE,
                )

        assert result == []

    @pytest.mark.asyncio
    async def test_discovery_brief_construction_from_dict(self):
        acts, _publish = _make_discover_activities(
            briefs=[
                {
                    "issuer_id": "i1",
                    "ticker_symbol": "PETR4",
                    "issuer_name": "Petrobras",
                    "sector": "Oil",
                    "market_cap": 1e12,
                    "screening_score": 0.95,
                    "anomaly_flags": ["flag1"],
                    "metrics": {"pe": 10},
                },
            ],
        )

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[DiscoverStocksWorkflow]):
                result = await env.client.execute_workflow(
                    DiscoverStocksWorkflow.run,
                    ScreenFilters(),
                    id="test-discover-4",
                    task_queue=TASK_QUEUE,
                )

        assert len(result) == 1
        assert isinstance(result[0], DiscoveryBrief)
        assert result[0].anomaly_flags == ["flag1"]
        assert result[0].metrics == {"pe": 10}

    @pytest.mark.asyncio
    async def test_publish_receives_correct_payload(self):
        acts, publish = _make_discover_activities(
            universe=[{"t": 1}, {"t": 2}, {"t": 3}],
            filtered=[{"t": 1}, {"t": 2}],
            briefs=[
                {
                    "issuer_id": "i1",
                    "ticker_symbol": "A",
                    "issuer_name": "A",
                    "sector": "S",
                    "market_cap": 1,
                    "screening_score": 1,
                    "anomaly_flags": [],
                    "metrics": {},
                },
            ],
        )

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[DiscoverStocksWorkflow]):
                await env.client.execute_workflow(
                    DiscoverStocksWorkflow.run,
                    ScreenFilters(),
                    id="test-discover-5",
                    task_queue=TASK_QUEUE,
                )

        assert len(publish) == 1
        p = publish[0]
        assert p["topic"] == "stocks.discovered"
        assert p["payload"]["total_universe"] == 3
        assert p["payload"]["after_filter"] == 2
        assert p["payload"]["briefs_count"] == 1
