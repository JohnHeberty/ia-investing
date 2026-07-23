from __future__ import annotations

import json
import logging
from collections.abc import Awaitable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ._decision import evaluate_decision
from ._extraction import evaluate_extraction
from ._interpretation import evaluate_interpretation

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    agent_name: str
    evaluation_type: str
    metric_name: str
    value: float
    expected: float | None = None
    passed: bool = False
    details: dict[str, Any] = field(default_factory=dict)


class AgentEvaluator:
    def __init__(self, golden_docs_path: str | None = None) -> None:
        self._golden_docs_path = Path(golden_docs_path) if golden_docs_path else None
        self._golden_docs: dict[str, Any] = {}
        if self._golden_docs_path and self._golden_docs_path.exists():
            self._load_golden_docs()

    def _load_golden_docs(self) -> None:
        try:
            self._golden_docs = json.loads(self._golden_docs_path.read_text(encoding="utf-8"))  # type: ignore[union-attr]
        except Exception:
            logger.exception("Failed to load golden docs from %s", self._golden_docs_path)

    def evaluate_extraction(
        self, agent_output: dict[str, Any], ground_truth: dict[str, Any]
    ) -> Awaitable[list[EvaluationResult]]:
        return evaluate_extraction(agent_output, ground_truth)

    def evaluate_interpretation(
        self, agent_output: dict[str, Any], expected_verdict: str
    ) -> Awaitable[list[EvaluationResult]]:
        return evaluate_interpretation(agent_output, expected_verdict)

    def evaluate_decision(
        self, agent_output: dict[str, Any], expected_action: str
    ) -> Awaitable[list[EvaluationResult]]:
        return evaluate_decision(agent_output, expected_action)

    def calculate_accuracy(self, results: list[EvaluationResult]) -> dict[str, object]:
        if not results:
            return {
                "total_metrics": 0,
                "passed": 0,
                "failed": 0,
                "accuracy": 0.0,
                "by_type": {},
                "by_metric": {},
            }

        passed = sum(1 for r in results if r.passed)
        total = len(results)

        by_type: dict[str, dict[str, int | float]] = {}
        for r in results:
            if r.evaluation_type not in by_type:
                by_type[r.evaluation_type] = {"total": 0, "passed": 0}
            by_type[r.evaluation_type]["total"] += 1
            if r.passed:
                by_type[r.evaluation_type]["passed"] += 1

        for v in by_type.values():
            v["accuracy"] = round(v["passed"] / v["total"], 4) if v["total"] > 0 else 0.0

        by_metric: dict[str, list[float]] = {}
        for r in results:
            by_metric.setdefault(r.metric_name, []).append(r.value)

        by_metric_avg = {k: round(sum(v) / len(v), 4) if v else 0.0 for k, v in by_metric.items()}

        return {
            "total_metrics": total,
            "passed": passed,
            "failed": total - passed,
            "accuracy": round(passed / total, 4) if total > 0 else 0.0,
            "by_type": by_type,
            "by_metric": by_metric_avg,
        }
