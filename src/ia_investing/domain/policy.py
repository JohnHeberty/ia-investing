from __future__ import annotations

import difflib
import hashlib
import json
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

LEGAL_TYPE_STAGE_TRANSITIONS: dict[str, dict[str, frozenset[str]]] = {
    "projeto_lei": {
        "discovered": frozenset({"introduced"}),
        "introduced": frozenset({"committee", "withdrawn"}),
        "committee": frozenset({"floor", "rejected"}),
        "floor": frozenset({"other_house", "approved", "rejected"}),
        "other_house": frozenset({"committee", "floor", "approved", "rejected"}),
        "approved": frozenset({"sanction", "veto"}),
        "sanction": frozenset({"published"}),
        "veto": frozenset({"veto_review", "published"}),
        "veto_review": frozenset({"published", "archived"}),
        "published": frozenset({"regulated", "revoked"}),
        "regulated": frozenset({"revoked"}),
        "withdrawn": frozenset(),
        "rejected": frozenset(),
        "revoked": frozenset(),
        "archived": frozenset(),
    },
    "decreto": {
        "discovered": frozenset({"published"}),
        "published": frozenset({"regulated", "revoked", "corrected"}),
        "regulated": frozenset({"revoked", "corrected"}),
        "corrected": frozenset({"revoked"}),
        "revoked": frozenset(),
    },
    "normativo": {
        "discovered": frozenset({"published"}),
        "published": frozenset({"regulated", "revoked", "corrected", "suspended"}),
        "regulated": frozenset({"revoked", "corrected", "suspended"}),
        "corrected": frozenset({"revoked", "regulated"}),
        "suspended": frozenset({"regulated", "revoked"}),
        "revoked": frozenset(),
    },
    "ato_oficial": {
        "discovered": frozenset({"published"}),
        "published": frozenset({"corrected", "revoked"}),
        "corrected": frozenset({"revoked"}),
        "revoked": frozenset(),
    },
}


def canonical_policy_key(authority: str, object_type: str, external_id: str) -> str:
    values = (authority.strip().lower(), object_type.strip().lower(), external_id.strip().lower())
    if not all(values):
        raise ValueError("policy identity requires authority, type, and external ID")
    return ":".join(values)


def validate_policy_stage_transition(current: str, target: str, legal_type: str | None = None) -> None:
    transitions = POLICY_STAGE_TRANSITIONS
    if legal_type and legal_type in LEGAL_TYPE_STAGE_TRANSITIONS:
        transitions = LEGAL_TYPE_STAGE_TRANSITIONS[legal_type]
    if target not in transitions.get(current, frozenset()):
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


@dataclass(frozen=True, slots=True)
class RectificationRecord:
    original_action_id: str
    rectifying_action_id: str
    rectification_type: str
    content_sha256: str
    knowledge_at: datetime

    def __post_init__(self) -> None:
        if self.rectification_type not in ("amendment", "rectification", "revocation", "veto_partial", "suspension"):
            raise ValueError(f"unknown rectification type: {self.rectification_type}")


@dataclass(frozen=True, slots=True)
class PolicyTheme:
    theme: str
    sector_exposures: tuple[str, ...]
    weight: Decimal
    confidence: Decimal


@dataclass(frozen=True, slots=True)
class PolicyDeadline:
    deadline_type: str
    due_date: datetime
    description: str
    is_extended: bool = False
    extension_date: datetime | None = None


def detect_rectification(
    original_text: str, amended_text: str, *, rectification_type: str
) -> dict[str, object] | None:
    diff = text_diff(original_text, amended_text)
    if not diff["changed"]:
        return None
    content_sha256 = hashlib.sha256(amended_text.encode()).hexdigest()
    return {
        "rectification_type": rectification_type,
        "diff": diff,
        "content_sha256": content_sha256,
        "additions": diff["additions"],
        "removals": diff["removals"],
    }


def compute_versioned_features(
    *,
    stage: str,
    legal_type: str,
    themes: tuple[PolicyTheme, ...],
    deadlines: tuple[PolicyDeadline, ...],
    base_rate: Decimal,
    corroboration_count: int,
    materiality: Decimal,
) -> dict[str, object]:
    return {
        "stage": stage,
        "legal_type": legal_type,
        "theme_count": len(themes),
        "themes": [t.theme for t in themes],
        "sector_exposures": list({s for t in themes for s in t.sector_exposures}),
        "deadline_count": len(deadlines),
        "nearest_deadline": min(
            (d.due_date for d in deadlines if d.due_date > datetime.now(d.due_date.tzinfo or None)),
            default=None,
        ),
        "base_rate": str(base_rate),
        "corroboration_count": corroboration_count,
        "materiality": str(materiality),
    }


def features_hash(features: dict[str, object]) -> str:
    canonical = json.dumps(features, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()
