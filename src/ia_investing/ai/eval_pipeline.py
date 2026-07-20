from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .eval_datasets import load_eval_dataset
from .eval_gate import CapabilityVersion, EvalGate
from .eval_runner import EvalRunner, EvalRunResult
from .evals import EvalThresholds, PromotionDecision
from .provider import AgentProvider


@dataclass(slots=True)
class ArtifactChange:
    capability: str
    old_version: CapabilityVersion
    new_version: CapabilityVersion


@dataclass(slots=True)
class PipelineResult:
    change: ArtifactChange
    requires_eval: bool
    eval_result: EvalRunResult | None
    promotion: PromotionDecision | None
    promoted: bool


@dataclass
class EvalPipeline:
    provider: AgentProvider
    dataset_path: Path
    thresholds: EvalThresholds | None = None

    def __post_init__(self) -> None:
        self._gate = EvalGate()
        self._runner = EvalRunner(provider=self.provider)

    async def validate_change(
        self,
        change: ArtifactChange,
        instructions_by_capability: dict[str, str],
        model: str,
        schemas_by_capability: dict[str, str],
    ) -> PipelineResult:
        requires_eval = self._gate.requires_eval(change.old_version, change.new_version)
        if not requires_eval:
            return PipelineResult(
                change=change,
                requires_eval=False,
                eval_result=None,
                promotion=None,
                promoted=False,
            )
        dataset, _hash = load_eval_dataset(self.dataset_path)
        run_results = await self._runner.run_eval_dataset(
            dataset,
            instructions_by_capability,
            model,
            schemas_by_capability,
        )
        eval_result = run_results.get(change.capability)
        if eval_result is None:
            return PipelineResult(
                change=change,
                requires_eval=True,
                eval_result=None,
                promotion=None,
                promoted=False,
            )
        thresholds = self.thresholds or EvalThresholds()
        baseline = eval_result.aggregate_metrics
        decision = self._gate.validate_promotion(
            change.capability,
            baseline,
            baseline,
            thresholds,
        )
        return PipelineResult(
            change=change,
            requires_eval=True,
            eval_result=eval_result,
            promotion=decision,
            promoted=decision.passed,
        )

    def validate_batch(self, changes: list[ArtifactChange]) -> list[ArtifactChange]:
        return [change for change in changes if self._gate.requires_eval(change.old_version, change.new_version)]
