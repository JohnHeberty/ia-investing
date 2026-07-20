from __future__ import annotations

import logging
from dataclasses import dataclass

from .evals import EvalMetrics, EvalThresholds, PromotionDecision, evaluate_promotion

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CapabilityVersion:
    prompt_hash: str
    schema_hash: str
    model_name: str
    toolset_hash: str


@dataclass(slots=True)
class EvalGate:
    def requires_eval(self, old: CapabilityVersion, new: CapabilityVersion) -> bool:
        return (
            old.prompt_hash != new.prompt_hash
            or old.schema_hash != new.schema_hash
            or old.model_name != new.model_name
            or old.toolset_hash != new.toolset_hash
        )

    def validate_promotion(
        self,
        capability: str,
        baseline_metrics: EvalMetrics,
        candidate_metrics: EvalMetrics,
        thresholds: EvalThresholds,
    ) -> PromotionDecision:
        decision = evaluate_promotion(baseline_metrics, candidate_metrics, thresholds)
        if decision.passed:
            logger.info(
                "eval promotion PASSED capability=%s schema_pass=%s citation_coverage=%s task_score=%s",
                capability,
                candidate_metrics.schema_pass,
                candidate_metrics.citation_coverage,
                candidate_metrics.task_score,
            )
        else:
            logger.warning(
                "eval promotion FAILED capability=%s failures=%s",
                capability,
                decision.failures,
            )
        return decision
