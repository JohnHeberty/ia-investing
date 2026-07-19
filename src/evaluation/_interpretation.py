"""Interpretation evaluation helpers."""

from __future__ import annotations

from ._evaluator import EvaluationResult


def _classification_accuracy(
    agent_output: dict,
    expected: str,
    agent_name: str,
    eval_type: str,
    field_key: str,
) -> list[EvaluationResult]:
    actual = agent_output.get(field_key, "").strip().lower()
    exp = expected.strip().lower()
    is_correct = actual == exp

    return [
        EvaluationResult(
            agent_name=agent_name,
            evaluation_type=eval_type,
            metric_name=f"classification_{field_key}",
            value=1.0 if is_correct else 0.0,
            expected=1.0,
            passed=is_correct,
            details={
                "field": field_key,
                "extracted": actual,
                "expected": exp,
                "exact_match": is_correct,
            },
        )
    ]


def _confidence_calibration(
    agent_output: dict,
    expected_correct: bool,
    agent_name: str,
    eval_type: str,
) -> list[EvaluationResult]:
    confidence = agent_output.get("confidence", 0.0)
    direction = agent_output.get("direction", "")
    calibration_error = abs(confidence - (1.0 if expected_correct else 0.0))

    return [
        EvaluationResult(
            agent_name=agent_name,
            evaluation_type=eval_type,
            metric_name="confidence_calibration",
            value=round(1.0 - calibration_error, 4),
            expected=1.0,
            passed=calibration_error <= 0.2,
            details={
                "confidence": confidence,
                "expected_correct": expected_correct,
                "calibration_error": round(calibration_error, 4),
                "direction": direction,
            },
        )
    ]


async def evaluate_interpretation(agent_output: dict, expected_verdict: str) -> list[EvaluationResult]:
    agent_name = agent_output.get("agent_name", "unknown")
    results: list[EvaluationResult] = []

    results.extend(_classification_accuracy(agent_output, expected_verdict, agent_name, "interpretation", "verdict"))

    results.extend(
        _confidence_calibration(
            agent_output,
            expected_verdict.lower() in ("positive", "bullish", "buy"),
            agent_name,
            "interpretation",
        )
    )

    reasoning = agent_output.get("reasoning", "")
    if isinstance(reasoning, str):
        has_reasoning = len(reasoning.strip()) > 20
        results.append(
            EvaluationResult(
                agent_name=agent_name,
                evaluation_type="interpretation",
                metric_name="reasoning_quality",
                value=1.0 if has_reasoning else 0.0,
                expected=1.0,
                passed=has_reasoning,
                details={
                    "reasoning_length": len(reasoning),
                    "has_substantive_reasoning": has_reasoning,
                },
            )
        )

    return results
