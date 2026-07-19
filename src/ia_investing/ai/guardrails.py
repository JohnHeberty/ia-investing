from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from .contracts import SpecialistOutput

_INJECTION_PATTERNS = (
    re.compile(r"ignore (all|any|the) previous instructions", re.IGNORECASE),
    re.compile(r"reveal (the )?(system prompt|secret|credential)", re.IGNORECASE),
    re.compile(r"execute (shell|sql|command)", re.IGNORECASE),
)
_PII_PATTERN = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")


class GuardrailViolationError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code


class RunBudget(BaseModel):
    max_prompt_tokens: int = Field(gt=0)
    max_completion_tokens: int = Field(gt=0)
    max_cost_usd: Decimal = Field(gt=0)
    max_turns: int = Field(gt=0)
    max_tool_calls: int = Field(gt=0)
    max_duration_ms: int = Field(gt=0)


@dataclass(slots=True)
class BudgetUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: Decimal = Decimal(0)
    turns: int = 0
    tool_calls: int = 0
    duration_ms: int = 0


def validate_untrusted_text(text: str) -> None:
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            raise GuardrailViolationError("prompt_injection", "Untrusted instructions were detected")
    if _PII_PATTERN.search(text):
        raise GuardrailViolationError("personal_data", "Personal data is not allowed in agent input")


def enforce_budget(budget: RunBudget, usage: BudgetUsage) -> None:
    limits = {
        "prompt_tokens": budget.max_prompt_tokens,
        "completion_tokens": budget.max_completion_tokens,
        "cost_usd": budget.max_cost_usd,
        "turns": budget.max_turns,
        "tool_calls": budget.max_tool_calls,
        "duration_ms": budget.max_duration_ms,
    }
    for field_name, limit in limits.items():
        if getattr(usage, field_name) > limit:
            raise GuardrailViolationError("budget_exceeded", f"Budget exceeded: {field_name}")


def validate_specialist_output(
    payload: dict[str, object],
    *,
    allowed_evidence_ids: set[UUID],
    expected_cutoff: object,
) -> SpecialistOutput:
    output = SpecialistOutput.model_validate(payload)
    if output.knowledge_cutoff != expected_cutoff:
        raise GuardrailViolationError("cutoff_mismatch", "Output changed the pinned knowledge cutoff")
    cited = {citation.evidence_id for finding in output.findings for citation in finding.citations}
    unknown = cited - allowed_evidence_ids
    if unknown:
        raise GuardrailViolationError("unknown_citation", "Output references evidence outside the authorized case")
    material = [finding for finding in output.findings if finding.confidence >= Decimal("0.5")]
    if material and any(not finding.citations for finding in material):
        raise GuardrailViolationError("citation_coverage", "Material findings require 100% citation coverage")
    return output
