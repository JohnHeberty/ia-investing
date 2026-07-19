from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TransformDefinition:
    version: str
    winsor_lower_quantile: float = 0.05
    winsor_upper_quantile: float = 0.95


def percentile(values: list[float], quantile: float) -> float:
    if not values or not 0 <= quantile <= 1:
        raise ValueError("percentile requires values and a quantile between zero and one")
    ordered = sorted(values)
    position = quantile * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def winsorize(values: list[float], definition: TransformDefinition) -> list[float]:
    lower = percentile(values, definition.winsor_lower_quantile)
    upper = percentile(values, definition.winsor_upper_quantile)
    return [min(max(value, lower), upper) for value in values]


def z_scores(values: list[float]) -> list[float]:
    if not values:
        raise ValueError("z-score requires values")
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    if variance == 0:
        return [0.0 for _ in values]
    standard_deviation = math.sqrt(variance)
    return [(value - mean) / standard_deviation for value in values]


def percentile_ranks(values: list[float]) -> list[float]:
    if not values:
        raise ValueError("percentile rank requires values")
    ordered = sorted(values)
    denominator = max(len(values) - 1, 1)
    return [ordered.index(value) / denominator for value in values]
