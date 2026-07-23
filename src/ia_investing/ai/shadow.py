from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from .provider import AgentProvider, ProviderError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ShadowResult:
    case_id: str
    baseline_output: dict[str, object]
    candidate_output: dict[str, object]
    baseline_error: str | None
    candidate_error: str | None
    diff_summary: str
    outputs_agree: bool


@dataclass(slots=True)
class ShadowRunner:
    provider: AgentProvider
    concurrency: int = 3

    async def shadow_run(
        self,
        case_id: str,
        input_payload: dict[str, object],
        baseline_instructions: str,
        baseline_model: str,
        baseline_schema: dict[str, object],
        candidate_instructions: str,
        candidate_model: str,
        candidate_schema: dict[str, object],
    ) -> ShadowResult:
        baseline_task = self._run_variant(
            "baseline", baseline_instructions, baseline_model, baseline_schema, input_payload
        )
        candidate_task = self._run_variant(
            "candidate", candidate_instructions, candidate_model, candidate_schema, input_payload
        )
        baseline_result, candidate_result = await asyncio.gather(baseline_task, candidate_task, return_exceptions=False)
        baseline_output = baseline_result.get("output", {}) if isinstance(baseline_result, dict) else {}
        candidate_output = candidate_result.get("output", {}) if isinstance(candidate_result, dict) else {}
        baseline_error = baseline_result.get("error") if isinstance(baseline_result, dict) else None
        candidate_error = candidate_result.get("error") if isinstance(candidate_result, dict) else None
        diff_summary = self._diff_outputs(baseline_output, candidate_output)  # type: ignore[arg-type]
        agree = baseline_output == candidate_output and baseline_error == candidate_error
        return ShadowResult(
            case_id=case_id,
            baseline_output=baseline_output,  # type: ignore[arg-type]
            candidate_output=candidate_output,  # type: ignore[arg-type]
            baseline_error=baseline_error,  # type: ignore[arg-type]
            candidate_error=candidate_error,  # type: ignore[arg-type]
            diff_summary=diff_summary,
            outputs_agree=agree,
        )

    async def _run_variant(
        self,
        label: str,
        instructions: str,
        model: str,
        schema: dict[str, object],
        input_payload: dict[str, object],
    ) -> dict[str, object]:
        try:
            response = await self.provider.complete(
                model=model,
                instructions=instructions,
                input_payload=input_payload,
                output_schema=schema,
            )
            return {"output": response.output, "error": None}
        except ProviderError as exc:
            logger.warning("shadow run %s failed: %s", label, exc.code)
            return {"output": {}, "error": exc.code}

    def _diff_outputs(self, baseline: dict[str, object], candidate: dict[str, object]) -> str:
        if baseline == candidate:
            return "identical"
        baseline_keys = set(baseline.keys())
        candidate_keys = set(candidate.keys())
        added = candidate_keys - baseline_keys
        removed = baseline_keys - candidate_keys
        changed = [k for k in baseline_keys & candidate_keys if baseline[k] != candidate[k]]
        parts: list[str] = []
        if added:
            parts.append(f"added={sorted(added)}")
        if removed:
            parts.append(f"removed={sorted(removed)}")
        if changed:
            parts.append(f"changed={sorted(changed)}")
        return "; ".join(parts) if parts else "structural_mismatch"
