from __future__ import annotations

from typing import Any

type LineItems = dict[str, Any]
type MarketData = dict[str, Any]
type MetricResult = dict[str, float | None]
type PillarResult = dict[str, MetricResult]
