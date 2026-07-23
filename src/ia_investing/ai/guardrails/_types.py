from __future__ import annotations

import enum
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from decimal import Decimal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_INJECTION_PATTERNS = (
    re.compile(r"ignore (all|any|the) previous instructions", re.IGNORECASE),
    re.compile(r"reveal (the )?(system prompt|secret|credential)", re.IGNORECASE),
    re.compile(r"execute (shell|sql|command)", re.IGNORECASE),
)
_PII_PATTERN = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")

_SUSPICIOUS_IMPERATIVES = re.compile(
    r"(?i)\b(ignore|disregard|forget|override|replace|bypass|skip|inject|pretend)\b",
)
_OBFUSCATED_ENTROPY_THRESHOLD = 5.5
_MIN_TEXT_LENGTH_FOR_ENTROPY = 40

_CONTENT_INDICATORS = {
    "untrusted_pdf": re.compile(r"(?i)%PDF-[\d.]+"),
    "untrusted_html": re.compile(r"(?i)<!DOCTYPE\s+html|<\s*html[\s>]"),
    "untrusted_user_input": re.compile(r"(?i)^(user|human|external)\s*[:>]"),
}

_MULTI_LANG_DISREGARD = re.compile(
    r"(?i)"
    r"(ignora\s+(todas|qualquer|as|instruções|instrucoes))|"
    r"(desconsidere(\s+(as|os|las|los|quaisquer))?\s+(instruções|instrucoes|instrucciones|órdenes|ordenes|comandos))|"
    r"(ignora\s+(tutte|qualsiasi|le|istruzioni))|"
    r"(请?忽略\s*(之前|所有|指令))|"
    r"(无视\s*(之前|所有|指令))",
)


@dataclass(frozen=True, slots=True)
class GuardrailViolation:
    code: str
    detail: str
    layer: str
    source_tag: str | None = None
    timestamp: float = field(default_factory=time.time)


class GuardrailViolationError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code

    def __str__(self) -> str:
        return f"{self.code}: {self.args[0]}"


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


class ContentSource(enum.Enum):
    TRUSTED_INTERNAL = "trusted_internal"
    UNTRUSTED_EXTERNAL = "untrusted_external"
    UNTRUSTED_USER = "untrusted_user"


class GuardrailLayer(enum.Enum):
    INPUT_CLASSIFICATION = "input_classification"
    SCHEMA_ENFORCEMENT = "schema_enforcement"
    ALLOWLIST = "allowlist"
    SEMANTIC = "semantic"
    APPROVAL_GATE = "approval_gate"


@dataclass(frozen=True, slots=True)
class GuardrailConfig:
    enabled_layers: frozenset[GuardrailLayer] = field(
        default_factory=lambda: frozenset(GuardrailLayer),
    )
    require_approval_for_sensitive: bool = True
    strict_schema_enforcement: bool = True
    enable_semantic_scan: bool = True
    max_suspicious_imperatives: int = 3


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    tool_name: str
    scope: str
    impact: dict[str, object]
    impact_hash: str
    requested_at: float = field(default_factory=time.time)


@dataclass(slots=True)
class ApprovalStore:
    _approvals: dict[str, ApprovalRequest] = field(default_factory=dict)

    def request(self, tool_name: str, scope: str, impact: dict[str, object]) -> ApprovalRequest:
        canonical = json.dumps(impact, sort_keys=True, separators=(",", ":"), default=str)
        impact_hash = hashlib.sha256(canonical.encode()).hexdigest()
        request = ApprovalRequest(
            tool_name=tool_name,
            scope=scope,
            impact=impact,
            impact_hash=impact_hash,
        )
        self._approvals[impact_hash] = request
        return request

    def resolve(self, impact_hash: str) -> ApprovalRequest | None:
        return self._approvals.get(impact_hash)
