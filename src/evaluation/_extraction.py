"""Extraction evaluation helpers."""

from __future__ import annotations

from difflib import SequenceMatcher

from ._evaluator import EvaluationResult


def _field_accuracy(
    extracted: dict[str, str | None],
    ground_truth: dict[str, str | None],
    agent_name: str,
    eval_type: str,
) -> list[EvaluationResult]:
    results: list[EvaluationResult] = []
    total = 0
    matched = 0

    for key, expected_val in ground_truth.items():
        total += 1
        extracted_val = extracted.get(key)
        is_match = False
        detail: dict = {
            "field": key,
            "extracted": extracted_val,
            "expected": expected_val,
        }

        if extracted_val is not None and expected_val is not None:
            if extracted_val == expected_val:
                is_match = True
                detail["match_type"] = "exact"
            else:
                similarity = SequenceMatcher(None, str(extracted_val), str(expected_val)).ratio()
                detail["similarity"] = round(similarity, 4)
                if similarity >= 0.85:
                    is_match = True
                    detail["match_type"] = "fuzzy"

        if is_match:
            matched += 1

        results.append(
            EvaluationResult(
                agent_name=agent_name,
                evaluation_type=eval_type,
                metric_name=f"field_{key}",
                value=1.0 if is_match else 0.0,
                expected=1.0,
                passed=is_match,
                details=detail,
            )
        )

    accuracy = matched / total if total > 0 else 0.0
    results.append(
        EvaluationResult(
            agent_name=agent_name,
            evaluation_type=eval_type,
            metric_name="overall_field_accuracy",
            value=round(accuracy, 4),
            expected=1.0,
            passed=accuracy >= 0.80,
            details={"total_fields": total, "matched_fields": matched},
        )
    )

    return results


async def evaluate_extraction(agent_output: dict, ground_truth: dict) -> list[EvaluationResult]:
    agent_name = agent_output.get("agent_name", "unknown")
    extracted_fields = agent_output.get("extracted_fields", agent_output)
    gt_fields = ground_truth.get("fields", ground_truth)

    return _field_accuracy(extracted_fields, gt_fields, agent_name, "extraction")
