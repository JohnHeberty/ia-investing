from __future__ import annotations

import difflib
import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

POLICY_STAGE_TRANSITIONS: dict[str, frozenset[str]] = {
    "discovered": frozenset({"introduced", "published", "archived"}),
    "introduced": frozenset({"committee", "withdrawn", "archived"}),
    "committee": frozenset({"floor", "rejected", "archived"}),
    "floor": frozenset({"other_house", "approved", "rejected"}),
    "other_house": frozenset({"committee", "floor", "approved", "rejected"}),
    "approved": frozenset({"sanction", "veto", "published"}),
    "sanction": frozenset({"published", "regulated"}),
    "veto": frozenset({"veto_review", "published"}),
    "veto_review": frozenset({"published", "archived"}),
    "published": frozenset({"corrected", "revoked", "regulated"}),
    "corrected": frozenset({"revoked", "regulated"}),
    "regulated": frozenset({"corrected", "revoked"}),
    "withdrawn": frozenset(),
    "rejected": frozenset(),
    "revoked": frozenset(),
    "archived": frozenset(),
}


def canonical_policy_key(authority: str, object_type: str, external_id: str) -> str:
    values = (authority.strip().lower(), object_type.strip().lower(), external_id.strip().lower())
    if not all(values):
        raise ValueError("policy identity requires authority, type, and external ID")
    return ":".join(values)


def validate_policy_stage_transition(current: str, target: str) -> None:
    if target not in POLICY_STAGE_TRANSITIONS.get(current, frozenset()):
        raise ValueError(f"invalid policy stage transition: {current} -> {target}")


def text_diff(previous: str, current: str) -> dict[str, object]:
    lines = list(
        difflib.unified_diff(
            previous.splitlines(), current.splitlines(), fromfile="previous", tofile="current", lineterm=""
        )
    )
    additions = sum(1 for line in lines if line.startswith("+") and not line.startswith("+++"))
    removals = sum(1 for line in lines if line.startswith("-") and not line.startswith("---"))
    return {"unified": lines, "additions": additions, "removals": removals, "changed": bool(additions or removals)}


@dataclass(frozen=True, slots=True)
class HistoricalOutcome:
    policy_type: str
    stage: str
    predicted_at: datetime
    outcome_at: datetime
    outcome: bool


@dataclass(frozen=True, slots=True)
class ProbabilityEstimate:
    probability: Decimal
    interval_low: Decimal
    interval_high: Decimal
    sample_size: int
    assumptions: tuple[str, ...]


def base_rate(
    outcomes: tuple[HistoricalOutcome, ...],
    *,
    policy_type: str,
    stage: str,
    knowledge_cutoff: datetime,
) -> ProbabilityEstimate:
    sample = [
        item
        for item in outcomes
        if item.policy_type == policy_type and item.stage == stage and item.outcome_at <= knowledge_cutoff
    ]
    successes = sum(item.outcome for item in sample)
    # Jeffreys-style smoothing avoids false certainty for small samples.
    probability = Decimal(successes + 1) / Decimal(len(sample) + 2)
    n = max(len(sample), 1)
    p = float(probability)
    z = 1.96
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator
    return ProbabilityEstimate(
        probability,
        Decimal(str(max(0.0, center - spread))).quantize(Decimal("0.0001")),
        Decimal(str(min(1.0, center + spread))).quantize(Decimal("0.0001")),
        len(sample),
        ("historical outcomes are filtered by outcome_at <= knowledge_cutoff", "interval uses Wilson score"),
    )


def brier_score(forecasts: tuple[tuple[Decimal, bool], ...]) -> Decimal:
    if not forecasts:
        raise ValueError("at least one resolved forecast is required")
    return sum(
        ((probability - Decimal(int(outcome))) ** 2 for probability, outcome in forecasts), start=Decimal(0)
    ) / Decimal(len(forecasts))


@dataclass(frozen=True, slots=True)
class ImpactEdge:
    source: str
    target: str
    relationship: str
    weight: Decimal
    confidence: Decimal
    status: str = "approved"


@dataclass(frozen=True, slots=True)
class PropagatedImpact:
    node: str
    impact: Decimal
    path: tuple[str, ...]


def propagate_impact(
    origin: str, initial_impact: Decimal, edges: tuple[ImpactEdge, ...]
) -> tuple[PropagatedImpact, ...]:
    approved = [edge for edge in edges if edge.status == "approved"]
    adjacency: dict[str, list[ImpactEdge]] = {}
    for edge in approved:
        if not Decimal(0) <= edge.confidence <= Decimal(1):
            raise ValueError("edge confidence must be between zero and one")
        adjacency.setdefault(edge.source, []).append(edge)
    results: list[PropagatedImpact] = []

    def visit(node: str, impact: Decimal, path: tuple[str, ...]) -> None:
        for edge in adjacency.get(node, []):
            if edge.target in path:
                raise ValueError(f"policy graph cycle detected: {' -> '.join((*path, edge.target))}")
            propagated = impact * edge.weight * edge.confidence
            next_path = (*path, edge.target)
            results.append(PropagatedImpact(edge.target, propagated, next_path))
            visit(edge.target, propagated, next_path)

    visit(origin, initial_impact, (origin,))
    return tuple(results)


def material_review_required(
    *,
    materiality: Decimal,
    exposure: Decimal,
    corroboration: Decimal,
    freshness: Decimal,
    threshold: Decimal = Decimal("0.20"),
) -> bool:
    if not all(Decimal(0) <= item <= Decimal(1) for item in (materiality, exposure, corroboration, freshness)):
        raise ValueError("policy alert inputs must be between zero and one")
    return materiality * exposure * corroboration * freshness >= threshold
