from __future__ import annotations

import logging
from dataclasses import dataclass, field
from uuid import UUID

from ._checks import (
    classify_content_source,
    validate_input_with_source,
    validate_specialist_output,
    validate_untrusted_text,
)
from ._types import (
    ApprovalRequest,
    ApprovalStore,
    ContentSource,
    GuardrailConfig,
    GuardrailLayer,
    GuardrailViolation,
    GuardrailViolationError,
)

logger = logging.getLogger(__name__)


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
            from ..contracts import CoordinatorOutput

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
