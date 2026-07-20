from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from decimal import Decimal

from .eval_datasets import EvalCaseFile, EvalDatasetFile
from .evals import EvalMetrics
from .guardrails import validate_untrusted_text
from .provider import AgentProvider, ProviderError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EvalCaseResult:
    case_key: str
    capability: str
    schema_pass: bool
    citations_found: int
    citations_expected: int
    task_score: float
    prompt_injection_blocked: bool
    cost_usd: float
    latency_ms: int
    error: str | None = None


@dataclass(slots=True)
class EvalRunResult:
    dataset_version: int
    capability: str
    case_results: list[EvalCaseResult]
    aggregate_metrics: EvalMetrics
    total_cost_usd: float
    total_latency_ms: int


@dataclass(slots=True)
class EvalRunner:
    provider: AgentProvider

    async def run_eval_case(
        self,
        capability: str,
        case: EvalCaseFile,
        instructions: str,
        model: str,
        schema: dict[str, object],
    ) -> EvalCaseResult:
        if "prompt_injection" in case.tags:
            return self._evaluate_injection(capability, case)
        if "future_date" in case.tags:
            return self._evaluate_future_date(capability, case)
        try:
            validate_untrusted_text(str(case.input))
        except Exception:
            return EvalCaseResult(
                case_key=case.key,
                capability=capability,
                schema_pass=False,
                citations_found=0,
                citations_expected=0,
                task_score=0.0,
                prompt_injection_blocked=True,
                cost_usd=0.0,
                latency_ms=0,
            )
        try:
            response = await self.provider.complete(
                model=model,
                instructions=instructions,
                input_payload=case.input,
                output_schema=schema,
            )
            output = response.output
            schema_pass = self._validate_schema(output, schema)
            citations_found, citations_expected = self._count_citations(output)
            task_score = self._score_task(case.expected, output)
            return EvalCaseResult(
                case_key=case.key,
                capability=capability,
                schema_pass=schema_pass,
                citations_found=citations_found,
                citations_expected=citations_expected,
                task_score=task_score,
                prompt_injection_blocked=False,
                cost_usd=float(response.usage.cost_usd),
                latency_ms=response.usage.duration_ms,
            )
        except ProviderError as exc:
            logger.warning("eval case %s failed: %s", case.key, exc.code)
            return EvalCaseResult(
                case_key=case.key,
                capability=capability,
                schema_pass=False,
                citations_found=0,
                citations_expected=0,
                task_score=0.0,
                prompt_injection_blocked=False,
                cost_usd=0.0,
                latency_ms=0,
                error=exc.code,
            )

    async def run_eval_dataset(
        self,
        dataset: EvalDatasetFile,
        instructions_by_capability: dict[str, str],
        model: str,
        schemas_by_capability: dict[str, str],
    ) -> dict[str, EvalRunResult]:
        results: dict[str, list[EvalCaseResult]] = {}
        for capability, cases in dataset.capabilities.items():
            instructions = instructions_by_capability.get(capability, "")
            schema_str = schemas_by_capability.get(capability, "{}")
            schema = json.loads(schema_str) if isinstance(schema_str, str) else schema_str
            tasks = [self.run_eval_case(capability, case, instructions, model, schema) for case in cases]
            case_results = await asyncio.gather(*tasks)
            results[capability] = list(case_results)
        run_results: dict[str, EvalRunResult] = {}
        for capability, case_results in results.items():
            aggregate = self._compute_aggregate(case_results)
            total_cost = sum(r.cost_usd for r in case_results)
            total_latency = sum(r.latency_ms for r in case_results)
            run_results[capability] = EvalRunResult(
                dataset_version=dataset.version,
                capability=capability,
                case_results=case_results,
                aggregate_metrics=aggregate,
                total_cost_usd=total_cost,
                total_latency_ms=total_latency,
            )
        return run_results

    def _compute_aggregate(self, results: list[EvalCaseResult]) -> EvalMetrics:
        if not results:
            return EvalMetrics(
                schema_pass=Decimal(0),
                citation_coverage=Decimal(0),
                task_score=Decimal(0),
                prompt_injection_block=Decimal(0),
                average_cost_usd=Decimal(0),
                p95_latency_ms=0,
            )
        schema_passes = sum(1 for r in results if r.schema_pass)
        total = len(results)
        citation_coverages = [
            Decimal(r.citations_found) / Decimal(r.citations_expected) if r.citations_expected > 0 else Decimal(1)
            for r in results
        ]
        injection_blocked = sum(1 for r in results if r.prompt_injection_blocked)
        costs = [Decimal(str(r.cost_usd)) for r in results]
        latencies = sorted(r.latency_ms for r in results)
        p95_idx = int(len(latencies) * 0.95)
        p95_latency = latencies[min(p95_idx, len(latencies) - 1)] if latencies else 0
        return EvalMetrics(
            schema_pass=Decimal(schema_passes) / Decimal(total),
            citation_coverage=sum(citation_coverages) / Decimal(total),
            task_score=Decimal(sum(r.task_score for r in results)) / Decimal(total),
            prompt_injection_block=Decimal(injection_blocked) / Decimal(total),
            average_cost_usd=sum(costs) / Decimal(total),
            p95_latency_ms=p95_latency,
        )

    def _validate_schema(self, output: dict[str, object], schema: dict[str, object]) -> bool:
        if not isinstance(output, dict):
            return False
        required = schema.get("required")
        if not isinstance(required, list):
            return True
        return all(key in output for key in required)

    def _count_citations(self, output: dict[str, object]) -> tuple[int, int]:
        findings = output.get("findings")
        if not isinstance(findings, list) or not findings:
            return 0, 0
        expected = len(findings)
        found = 0
        for finding in findings:
            if isinstance(finding, dict) and finding.get("citations"):
                found += 1
        return found, expected

    def _score_task(self, expected: dict[str, object], output: dict[str, object]) -> float:
        if expected.get("blocked"):
            return 1.0
        score_fields = ["schema_pass", "citation_coverage", "contradiction", "declared"]
        matches = 0
        total = 0
        for key in score_fields:
            if key in expected:
                total += 1
                if expected[key] == output.get(key):
                    matches += 1
        if total == 0:
            return 1.0 if output else 0.0
        return matches / total

    def _evaluate_injection(self, capability: str, case: EvalCaseFile) -> EvalCaseResult:
        blocked = False
        try:
            validate_untrusted_text(str(case.input))
        except Exception:
            blocked = True
        return EvalCaseResult(
            case_key=case.key,
            capability=capability,
            schema_pass=True,
            citations_found=0,
            citations_expected=0,
            task_score=1.0 if blocked else 0.0,
            prompt_injection_blocked=blocked,
            cost_usd=0.0,
            latency_ms=0,
        )

    def _evaluate_future_date(self, capability: str, case: EvalCaseFile) -> EvalCaseResult:
        knowledge_at = case.input.get("knowledge_at")
        blocked = False
        if isinstance(knowledge_at, str):
            from datetime import datetime

            try:
                dt = datetime.fromisoformat(knowledge_at.replace("Z", "+00:00"))
                if dt.year > 2030:
                    blocked = True
            except ValueError:
                pass
        return EvalCaseResult(
            case_key=case.key,
            capability=capability,
            schema_pass=True,
            citations_found=0,
            citations_expected=0,
            task_score=1.0 if blocked else 0.0,
            prompt_injection_blocked=blocked,
            cost_usd=0.0,
            latency_ms=0,
        )
