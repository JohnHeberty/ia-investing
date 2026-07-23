from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .eval_datasets import EvalDatasetFile
from .eval_gate import EvalGate
from .eval_runner import EvalRunner
from .evals import EvalMetrics, EvalThresholds, PromotionDecision
from .provider import AgentProvider
from .shadow import ShadowResult, ShadowRunner


@dataclass(frozen=True, slots=True)
class ShadowGateConfig:
    baseline_model: str
    candidate_model: str
    instructions_by_capability: dict[str, str]
    schemas_by_capability: dict[str, dict[str, object]]
    eval_dataset: EvalDatasetFile | None = None
    thresholds: EvalThresholds = field(default_factory=EvalThresholds)


@dataclass(frozen=True, slots=True)
class ShadowGateResult:
    capability: str
    shadow_result: ShadowResult
    eval_passed: bool = True
    promotion_decision: PromotionDecision | None = None
    gate_open: bool = False


class ShadowGate:
    def __init__(self, provider: AgentProvider) -> None:
        self._provider = provider
        self._shadow = ShadowRunner(provider=provider)
        self._eval_runner = EvalRunner(provider=provider)
        self._eval_gate = EvalGate()

    async def run_shadow_gate(
        self,
        case_id: str,
        input_payload: dict[str, Any],
        config: ShadowGateConfig,
    ) -> ShadowGateResult:
        capability = case_id.split("/")[0]
        instructions = config.instructions_by_capability[capability]
        schema = config.schemas_by_capability[capability]
        shadow_result = await self._shadow.shadow_run(
            case_id=case_id,
            input_payload=input_payload,
            baseline_instructions=instructions,
            baseline_model=config.baseline_model,
            baseline_schema=schema,
            candidate_instructions=instructions,
            candidate_model=config.candidate_model,
            candidate_schema=schema,
        )
        eval_passed = True
        promotion_decision: PromotionDecision | None = None
        if config.eval_dataset is not None:
            eval_results = await self._eval_runner.run_eval_dataset(
                dataset=config.eval_dataset,
                instructions_by_capability=config.instructions_by_capability,
                model=config.candidate_model,
                schemas_by_capability={k: json.dumps(v) for k, v in config.schemas_by_capability.items()},
            )
            if capability in eval_results:
                baseline_metrics = EvalMetrics(
                    schema_pass=Decimal("1"),
                    citation_coverage=Decimal("1"),
                    task_score=Decimal("1"),
                    prompt_injection_block=Decimal("1"),
                    average_cost_usd=Decimal("0"),
                    p95_latency_ms=0,
                )
                promotion_decision = self._eval_gate.validate_promotion(
                    capability=capability,
                    baseline_metrics=baseline_metrics,
                    candidate_metrics=eval_results[capability].aggregate_metrics,
                    thresholds=config.thresholds,
                )
                eval_passed = promotion_decision.passed
        gate_open = shadow_result.outputs_agree and eval_passed
        return ShadowGateResult(
            capability=capability,
            shadow_result=shadow_result,
            eval_passed=eval_passed,
            promotion_decision=promotion_decision,
            gate_open=gate_open,
        )

    async def batch_shadow_gate(
        self,
        cases: list[tuple[str, dict[str, Any]]],
        config: ShadowGateConfig,
    ) -> list[ShadowGateResult]:
        tasks = [self.run_shadow_gate(case_id, input_payload, config) for case_id, input_payload in cases]
        return list(await asyncio.gather(*tasks))
