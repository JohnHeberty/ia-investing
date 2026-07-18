"""Decision evaluation helpers."""

from __future__ import annotations

from ._evaluator import EvaluationResult
from ._interpretation import _classification_accuracy


async def evaluate_decision(
    agent_output: dict, expected_action: str
) -> list[EvaluationResult]:
    agent_name = agent_output.get("agent_name", "unknown")
    results: list[EvaluationResult] = []

    results.extend(
        _classification_accuracy(
            agent_output, expected_action, agent_name, "decision", "action"
        )
    )

    size = agent_output.get("position_size_pct")
    if size is not None:
        size_val = float(size)
        size_ok = 0.0 <= size_val <= 0.10
        results.append(
            EvaluationResult(
                agent_name=agent_name,
                evaluation_type="decision",
                metric_name="position_sizing",
                value=1.0 if size_ok else 0.0,
                expected=1.0,
                passed=size_ok,
                details={"position_size_pct": size_val, "within_limits": size_ok},
            )
        )

    has_rationale = bool(agent_output.get("rationale"))
    results.append(
        EvaluationResult(
            agent_name=agent_name,
            evaluation_type="decision",
            metric_name="has_rationale",
            value=1.0 if has_rationale else 0.0,
            expected=1.0,
            passed=has_rationale,
            details={"has_rationale": has_rationale},
        )
    )

    return results
