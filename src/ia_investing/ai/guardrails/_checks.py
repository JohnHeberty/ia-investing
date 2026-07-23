from __future__ import annotations

import base64
import logging
import math
import re
from decimal import Decimal
from uuid import UUID

from ..contracts import SpecialistOutput
from ._types import (
    _CONTENT_INDICATORS,
    _INJECTION_PATTERNS,
    _MIN_TEXT_LENGTH_FOR_ENTROPY,
    _MULTI_LANG_DISREGARD,
    _OBFUSCATED_ENTROPY_THRESHOLD,
    _PII_PATTERN,
    _SUSPICIOUS_IMPERATIVES,
    BudgetUsage,
    ContentSource,
    GuardrailConfig,
    GuardrailViolation,
    GuardrailViolationError,
    RunBudget,
)

logger = logging.getLogger(__name__)


def _record(violations: list[GuardrailViolation] | None, code: str, detail: str) -> None:
    if violations is not None:
        violations.append(GuardrailViolation(code=code, detail=detail, layer="semantic"))


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
