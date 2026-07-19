from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .contracts import CommandReceipt
from .guardrails import validate_untrusted_text

FORBIDDEN_TOOL_NAMES = frozenset({"sql", "shell", "filesystem", "secrets", "broker", "internet"})


class ToolPolicyError(PermissionError):
    pass


class ToolApprovalRequiredError(ToolPolicyError):
    pass


@dataclass(frozen=True, slots=True)
class TypedTool[InputT: BaseModel, OutputT: BaseModel]:
    name: str
    version: int
    input_type: type[InputT]
    output_type: type[OutputT]
    handler: Callable[[InputT], Awaitable[OutputT]]
    sensitive: bool = False


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, TypedTool[BaseModel, BaseModel]] = {}

    def register[InputT: BaseModel, OutputT: BaseModel](self, tool: TypedTool[InputT, OutputT]) -> None:
        normalized = tool.name.strip().lower()
        if normalized in FORBIDDEN_TOOL_NAMES or any(term in normalized for term in FORBIDDEN_TOOL_NAMES):
            raise ToolPolicyError(f"Forbidden tool capability: {tool.name}")
        if normalized in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[normalized] = tool  # type: ignore[assignment]

    def allowed(self, names: set[str]) -> dict[str, TypedTool[BaseModel, BaseModel]]:
        unknown = names - self._tools.keys()
        if unknown:
            raise ToolPolicyError(f"Unknown or forbidden tools requested: {sorted(unknown)}")
        return {name: self._tools[name] for name in sorted(names)}

    async def invoke(
        self,
        name: str,
        raw_input: dict[str, object],
        *,
        allowlist: set[str],
        approval: CommandReceipt | None = None,
    ) -> BaseModel:
        normalized = name.strip().lower()
        if normalized not in allowlist or normalized not in self._tools:
            raise ToolPolicyError(f"Tool is not allowed: {name}")
        validate_untrusted_text(json.dumps(raw_input, ensure_ascii=False, default=str))
        tool = self._tools[normalized]
        if tool.sensitive:
            expected_hash = hashlib.sha256(
                json.dumps(raw_input, sort_keys=True, separators=(",", ":"), default=str).encode()
            ).hexdigest()
            if (
                approval is None
                or approval.status != "accepted"
                or approval.command.strip().lower() != normalized
                or approval.impact_hash != expected_hash
                or not approval.scope.strip()
            ):
                raise ToolApprovalRequiredError(f"Sensitive tool requires an accepted scoped approval: {name}")
        typed_input = tool.input_type.model_validate(raw_input)
        return tool.output_type.model_validate(await tool.handler(typed_input))


def command_receipt(command: str, scope: str, impact: dict[str, object]) -> CommandReceipt:
    canonical = json.dumps(impact, sort_keys=True, separators=(",", ":"), default=str)
    return CommandReceipt(
        command_id=uuid4(),
        command=command,
        status="awaiting_approval",
        scope=scope,
        impact_hash=hashlib.sha256(canonical.encode()).hexdigest(),
    )


class FinancialMetricsInput(BaseModel):
    issuer_id: UUID
    reporting_period_id: UUID | None = None
    metric_names: list[str] = Field(min_length=1, max_length=50)
    as_of: datetime


class FinancialMetricsOutput(BaseModel):
    observations: list[dict[str, object]]


class EvidenceSearchInput(BaseModel):
    case_id: UUID
    query: str = Field(min_length=1, max_length=1_000)
    knowledge_cutoff: datetime
    limit: int = Field(default=10, ge=1, le=50)


class EvidenceSearchOutput(BaseModel):
    evidence: list[dict[str, object]]


class ValuationInput(BaseModel):
    thesis_version_id: UUID | None = None
    model_type: str = Field(pattern=r"^dcf$")
    assumptions: dict[str, object]


class ValuationOutput(BaseModel):
    results: list[dict[str, object]]
