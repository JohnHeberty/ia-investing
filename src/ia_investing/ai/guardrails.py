from __future__ import annotations

import base64
import enum
import json
import logging
import math
import re
import time
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from .contracts import SpecialistOutput

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


# ---------------------------------------------------------------------------
# Layer 1 — Input classification
# ---------------------------------------------------------------------------


def classify_content_source(
    content: str,
    *,
    origin_hint: str | None = None,
) -> ContentSource:
    if origin_hint:
        lower = origin_hint.lower()
        if lower in {"internal", "database", "api_internal", "system"}:
            return ContentSource.TRUSTED_INTERNAL
        if lower in {"pdf", "html", "web", "external_api", "scraper"}:
            return ContentSource.UNTRUSTED_EXTERNAL
        if lower in {"user_input", "form", "message", "chat"}:
            return ContentSource.UNTRUSTED_USER
    if _CONTENT_INDICATORS["untrusted_pdf"].search(content):
        return ContentSource.UNTRUSTED_EXTERNAL
    if _CONTENT_INDICATORS["untrusted_html"].search(content):
        return ContentSource.UNTRUSTED_EXTERNAL
    if _CONTENT_INDICATORS["untrusted_user_input"].search(content):
        return ContentSource.UNTRUSTED_USER
    return ContentSource.UNTRUSTED_USER


def validate_input_with_source(
    text: str,
    source: ContentSource,
    *,
    config: GuardrailConfig | None = None,
    violations: list[GuardrailViolation] | None = None,
) -> None:
    if source == ContentSource.TRUSTED_INTERNAL:
        return
    if config is None or config.enable_semantic_scan:
        _check_obfuscated_content(text, violations=violations)
        _check_multi_lang_injection(text, violations=violations)


# ---------------------------------------------------------------------------
# Layer 4 — Semantic guardrail (beyond regex)
# ---------------------------------------------------------------------------


def _shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    cleaned = re.sub(r"\s+", "", text)
    length = len(cleaned)
    if length == 0:
        return 0.0
    freq: dict[str, int] = {}
    for ch in cleaned:
        freq[ch] = freq.get(ch, 0) + 1
    return -sum((count / length) * math.log2(count / length) for count in freq.values())


def _has_heavy_base64(text: str) -> bool:
    b64_candidates = re.findall(r"[A-Za-z0-9+/=]{40,}", text)
    for candidate in b64_candidates:
        try:
            decoded = base64.b64decode(candidate)
            decoded_text = decoded.decode("utf-8", errors="replace")
            if any(p.search(decoded_text) for p in _INJECTION_PATTERNS):
                return True
            if _SUSPICIOUS_IMPERATIVES.search(decoded_text):
                return True
        except Exception:
            continue
    return False


def _has_hex_encoded_instructions(text: str) -> bool:
    hex_sequences = re.findall(r"(?:0x[0-9a-fA-F]{2})+|(?:[0-9a-fA-F]{2}\s){10,}", text)
    for seq in hex_sequences:
        clean = re.sub(r"\s|0x", "", seq)
        try:
            decoded = bytes.fromhex(clean).decode("utf-8", errors="replace")
            if _SUSPICIOUS_IMPERATIVES.search(decoded):
                return True
        except ValueError:
            continue
    return False


def _check_obfuscated_content(
    text: str,
    *,
    violations: list[GuardrailViolation] | None = None,
) -> bool:
    if len(text) < _MIN_TEXT_LENGTH_FOR_ENTROPY:
        return False
    entropy = _shannon_entropy(text)
    if entropy > _OBFUSCATED_ENTROPY_THRESHOLD and _SUSPICIOUS_IMPERATIVES.search(text):
        _record(violations, "obfuscated_content", "Content has high entropy with suspicious imperatives")
        raise GuardrailViolationError("obfuscated_content", "Content appears obfuscated with suspicious instructions")
    if _has_heavy_base64(text):
        _record(violations, "base64_injection", "Base64-encoded content contains injection patterns")
        raise GuardrailViolationError("base64_injection", "Base64-encoded injection detected")
    if _has_hex_encoded_instructions(text):
        _record(violations, "hex_encoded_injection", "Hex-encoded content contains injection patterns")
        raise GuardrailViolationError("hex_encoded_injection", "Hex-encoded injection detected")
    return False


def _check_multi_lang_injection(
    text: str,
    *,
    violations: list[GuardrailViolation] | None = None,
) -> bool:
    if _MULTI_LANG_DISREGARD.search(text):
        _record(violations, "multi_lang_injection", "Non-English disregard instruction detected")
        raise GuardrailViolationError("multi_lang_injection", "Multi-language injection detected")
    return False


def _check_semantic_content(
    text: str,
    *,
    config: GuardrailConfig,
    violations: list[GuardrailViolation] | None = None,
) -> None:
    if _check_obfuscated_content(text, violations=violations):
        return
    if _check_multi_lang_injection(text, violations=violations):
        return
    imperative_matches = _SUSPICIOUS_IMPERATIVES.findall(text)
    if len(imperative_matches) >= config.max_suspicious_imperatives:
        _record(violations, "excessive_imperatives", f"Found {len(imperative_matches)} suspicious imperative verbs")
        raise GuardrailViolationError(
            "excessive_imperatives",
            f"Content contains {len(imperative_matches)} suspicious imperative verbs",
        )


# ---------------------------------------------------------------------------
# Layer 5 — Approval gates
# ---------------------------------------------------------------------------


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
        import hashlib

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


# ---------------------------------------------------------------------------
# Guardrail engine (composes all layers)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class GuardrailReporter:
    violations: list[GuardrailViolation] = field(default_factory=list)
    _tripped_layers: set[str] = field(default_factory=set)

    def record(self, violation: GuardrailViolation) -> None:
        self.violations.append(violation)
        self._tripped_layers.add(violation.layer)
        logger.warning(
            "guardrail trip layer=%s code=%s detail=%s source=%s",
            violation.layer,
            violation.code,
            violation.detail,
            violation.source_tag,
        )

    @property
    def tripped(self) -> bool:
        return len(self.violations) > 0

    @property
    def tripped_layers(self) -> frozenset[str]:
        return frozenset(self._tripped_layers)

    def summary(self) -> dict[str, object]:
        return {
            "total_violations": len(self.violations),
            "tripped_layers": sorted(self._tripped_layers),
            "violations": [
                {
                    "code": v.code,
                    "layer": v.layer,
                    "source_tag": v.source_tag,
                }
                for v in self.violations
            ],
        }


def _record(violations: list[GuardrailViolation] | None, code: str, detail: str) -> None:
    if violations is not None:
        violations.append(GuardrailViolation(code=code, detail=detail, layer="semantic"))


class GuardrailEngine:
    def __init__(self, config: GuardrailConfig | None = None) -> None:
        self.config = config or GuardrailConfig()
        self.reporter = GuardrailReporter()
        self.approval_store = ApprovalStore()

    def check_input(
        self,
        text: str,
        *,
        origin_hint: str | None = None,
        source: ContentSource | None = None,
    ) -> ContentSource:
        effective_source = source if source is not None else classify_content_source(text, origin_hint=origin_hint)
        if GuardrailLayer.INPUT_CLASSIFICATION not in self.config.enabled_layers:
            return effective_source
        if effective_source == ContentSource.TRUSTED_INTERNAL:
            return effective_source
        if GuardrailLayer.SEMANTIC in self.config.enabled_layers and self.config.enable_semantic_scan:
            try:
                validate_input_with_source(
                    text,
                    effective_source,
                    config=self.config,
                    violations=self.reporter.violations,
                )
            except GuardrailViolationError as exc:
                self.reporter.record(
                    GuardrailViolation(
                        code=exc.code,
                        detail=str(exc),
                        layer="semantic",
                        source_tag=effective_source.value,
                    ),
                )
                raise
        try:
            validate_untrusted_text(text)
        except GuardrailViolationError as exc:
            self.reporter.record(
                GuardrailViolation(
                    code=exc.code,
                    detail=str(exc),
                    layer="input_classification",
                    source_tag=effective_source.value,
                ),
            )
            raise
        return effective_source

    def check_output(
        self,
        payload: dict[str, object],
        capability: str,
        *,
        allowed_evidence_ids: set[UUID] | None = None,
        expected_cutoff: object = None,
    ) -> dict[str, object]:
        if GuardrailLayer.SCHEMA_ENFORCEMENT not in self.config.enabled_layers:
            return payload
        if capability in {"filing", "news", "macro", "political", "critic"}:
            try:
                output = validate_specialist_output(
                    payload,
                    allowed_evidence_ids=allowed_evidence_ids or set(),
                    expected_cutoff=expected_cutoff,
                )
                if output.capability != capability:
                    raise GuardrailViolationError("capability_mismatch", "Output capability does not match pinned run")
                return output.model_dump(mode="json")
            except GuardrailViolationError as exc:
                self.reporter.record(
                    GuardrailViolation(code=exc.code, detail=str(exc), layer="schema_enforcement"),
                )
                raise
        if capability == "research_coordinator":
            from .contracts import CoordinatorOutput

            try:
                return CoordinatorOutput.model_validate(payload).model_dump(mode="json")
            except Exception as exc:
                raise GuardrailViolationError(
                    "coordinator_schema",
                    f"Coordinator output validation failed: {exc}",
                ) from exc
        return payload

    def require_approval(
        self,
        tool_name: str,
        scope: str,
        impact: dict[str, object],
    ) -> ApprovalRequest:
        if (
            GuardrailLayer.APPROVAL_GATE not in self.config.enabled_layers
            or not self.config.require_approval_for_sensitive
        ):
            raise GuardrailViolationError("approval_disabled", "Approval gate is not enabled")
        request = self.approval_store.request(tool_name, scope, impact)
        self.reporter.record(
            GuardrailViolation(
                code="approval_required",
                detail=f"Approval required for {tool_name} in scope {scope}",
                layer="approval_gate",
            ),
        )
        return request

    def check_allowlist(
        self,
        tool_name: str,
        allowlist: set[str],
    ) -> None:
        if GuardrailLayer.ALLOWLIST not in self.config.enabled_layers:
            return
        normalized = tool_name.strip().lower()
        if normalized not in allowlist:
            self.reporter.record(
                GuardrailViolation(
                    code="tool_not_allowed",
                    detail=f"Tool '{tool_name}' is not in the allowlist",
                    layer="allowlist",
                ),
            )
            raise GuardrailViolationError("tool_not_allowed", f"Tool is not allowed: {tool_name}")

    def reset(self) -> None:
        self.reporter = GuardrailReporter()
        self.approval_store = ApprovalStore()


# ---------------------------------------------------------------------------
# Existing public API (preserved for backward compatibility)
# ---------------------------------------------------------------------------


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
