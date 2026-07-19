from __future__ import annotations

from collections.abc import Awaitable, Callable
from decimal import Decimal

from .contracts import CoordinatorOutput, ResearchPlan, SpecialistOutput
from .guardrails import BudgetUsage, RunBudget, enforce_budget

SPECIALIST_CAPABILITIES = frozenset({"filing", "news", "macro", "political", "critic"})
SpecialistExecutor = Callable[[str, str], Awaitable[SpecialistOutput]]


class ResearchCoordinator:
    def __init__(self, specialist_executor: SpecialistExecutor, budget: RunBudget) -> None:
        self.specialist_executor = specialist_executor
        self.budget = budget

    async def execute(self, plan: ResearchPlan) -> CoordinatorOutput:
        usage = BudgetUsage()
        outputs: list[SpecialistOutput] = []
        failures: list[str] = []
        for step in plan.steps:
            if step.capability not in SPECIALIST_CAPABILITIES:
                raise PermissionError(f"coordinator cannot delegate capability: {step.capability}")
            usage.tool_calls += 1
            usage.turns += 1
            enforce_budget(self.budget, usage)
            try:
                output = await self.specialist_executor(step.capability, step.question)
            except Exception:
                failures.append(step.capability)
                if step.required:
                    continue
            else:
                if output.capability != step.capability or output.knowledge_cutoff != plan.knowledge_cutoff:
                    raise ValueError("specialist changed its pinned capability or knowledge cutoff")
                outputs.append(output)

        findings = [finding for output in outputs for finding in output.findings]
        contradictions = list(
            dict.fromkeys(contradiction for output in outputs for contradiction in output.contradictions)
        )
        confidence = (
            sum((finding.confidence for finding in findings), start=Decimal(0)) / Decimal(len(findings))
            if findings
            else Decimal(0)
        )
        return CoordinatorOutput(
            plan=plan,
            specialist_outputs=outputs,
            consolidated_findings=findings,
            unresolved_contradictions=contradictions,
            confidence=confidence,
            partial_failure_capabilities=failures,
        )
