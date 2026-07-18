from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from temporalio import workflow


@dataclass(slots=True)
class ScreenFilters:
    min_market_cap: float = 0.0
    max_market_cap: float = float("inf")
    sectors_include: list[str] = field(default_factory=list)
    sectors_exclude: list[str] = field(default_factory=list)
    min_volume_avg: float = 0.0
    exclude_penny_stocks: bool = True


@dataclass(slots=True)
class DiscoveryBrief:
    issuer_id: str
    ticker_symbol: str
    issuer_name: str
    sector: str
    market_cap: float
    screening_score: float
    anomaly_flags: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


@workflow.defn
class DiscoverStocksWorkflow:

    @workflow.run
    async def run(self, filters: ScreenFilters) -> list[DiscoveryBrief]:
        universe = await workflow.execute_activity(
            "fetch_b3_universe",
            args=[],
            start_to_close_timeout=timedelta(seconds=120),
        )

        filtered = await workflow.execute_activity(
            "apply_screen_filters",
            args=[universe, {
                "min_market_cap": filters.min_market_cap,
                "max_market_cap": filters.max_market_cap,
                "sectors_include": filters.sectors_include,
                "sectors_exclude": filters.sectors_exclude,
                "min_volume_avg": filters.min_volume_avg,
                "exclude_penny_stocks": filters.exclude_penny_stocks,
            }],
            start_to_close_timeout=timedelta(seconds=60),
        )

        scored = await workflow.execute_activity(
            "calculate_screening_metrics",
            args=[filtered],
            start_to_close_timeout=timedelta(seconds=180),
        )

        anomalies = await workflow.execute_activity(
            "identify_anomalies",
            args=[scored],
            start_to_close_timeout=timedelta(seconds=60),
        )

        briefs = await workflow.execute_activity(
            "generate_discovery_briefs",
            args=[scored, anomalies],
            start_to_close_timeout=timedelta(seconds=60),
        )

        results = [
            DiscoveryBrief(
                issuer_id=b.get("issuer_id", ""),
                ticker_symbol=b.get("ticker_symbol", ""),
                issuer_name=b.get("issuer_name", ""),
                sector=b.get("sector", ""),
                market_cap=b.get("market_cap", 0.0),
                screening_score=b.get("screening_score", 0.0),
                anomaly_flags=b.get("anomaly_flags", []),
                metrics=b.get("metrics", {}),
            )
            for b in briefs
        ]

        await workflow.execute_activity(
            "publish_event",
            args=[
                "stocks.discovered",
                {
                    "total_universe": len(universe),
                    "after_filter": len(filtered),
                    "briefs_count": len(results),
                    "anomalies_count": sum(len(b.anomaly_flags) for b in results),
                },
            ],
            start_to_close_timeout=timedelta(seconds=10),
        )

        return results
