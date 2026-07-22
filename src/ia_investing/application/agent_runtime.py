from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.agent_runtime import (
    AgentApprovalRequest,
    AgentArtifact,
    AgentCapability,
    AgentEvalRun,
    AgentPromotion,
    AgentRuntimeRun,
    AgentRuntimeToolCall,
    AgentVersion,
)
from database.models.agents import AuditLog
from ia_investing.ai.artifacts import ArtifactLoader, CapabilityManifest, FileArtifact


def canonical_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


SENSITIVE_ARGUMENT_KEYS = frozenset({"password", "secret", "token", "api_key", "authorization", "cookie"})


def sanitize_tool_payload(value: object, *, key: str = "") -> object:
    if key.lower() in SENSITIVE_ARGUMENT_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(item_key): sanitize_tool_payload(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_tool_payload(item) for item in value]
    if isinstance(value, str) and len(value) > 4_000:
        return value[:4_000] + "…[TRUNCATED]"
    return value


class AgentRegistryService:
    def __init__(self, session: AsyncSession, loader: ArtifactLoader) -> None:
        self.session = session
        self.loader = loader

    async def synchronize(self, actor_id: str) -> list[AgentVersion]:
        registry = self.loader.load_registry()
        synchronized: list[AgentVersion] = []
        for manifest in registry.capabilities:
            capability = (
                await self.session.execute(
                    select(AgentCapability).where(AgentCapability.logical_id == manifest.logical_id)
                )
            ).scalar_one_or_none()
            if capability is None:
                capability = AgentCapability(
                    logical_id=manifest.logical_id,
                    display_name=manifest.logical_id.replace("_", " ").title(),
                    description=f"Versioned runtime capability: {manifest.logical_id}",
                )
                self.session.add(capability)
                await self.session.flush()

            prompt = await self._file_artifact(manifest, "prompt", manifest.prompt, actor_id)
            schema = await self._file_artifact(manifest, "schema", manifest.schema_, actor_id)
            model = await self._inline_artifact(
                manifest,
                "model_profile",
                manifest.model_profile.model_dump(mode="json"),
                actor_id,
            )
            toolset = await self._inline_artifact(manifest, "toolset", {"tools": manifest.tools}, actor_id)
            version = (
                await self.session.execute(
                    select(AgentVersion).where(
                        AgentVersion.capability_id == capability.id,
                        AgentVersion.prompt_artifact_id == prompt.id,
                        AgentVersion.schema_artifact_id == schema.id,
                        AgentVersion.model_artifact_id == model.id,
                        AgentVersion.toolset_artifact_id == toolset.id,
                    )
                )
            ).scalar_one_or_none()
            if version is None:
                next_version = (
                    await self.session.scalar(
                        select(func.coalesce(func.max(AgentVersion.version), 0) + 1).where(
                            AgentVersion.capability_id == capability.id
                        )
                    )
                ) or 1
                initial = capability.active_version_id is None
                version = AgentVersion(
                    capability_id=capability.id,
                    version=next_version,
                    prompt_artifact_id=prompt.id,
                    schema_artifact_id=schema.id,
                    model_artifact_id=model.id,
                    toolset_artifact_id=toolset.id,
                    budgets={
                        "max_prompt_tokens": 16_000,
                        "max_completion_tokens": 8_000,
                        "max_cost_usd": "2.00",
                        "max_turns": 8,
                        "max_tool_calls": 20,
                        "max_duration_ms": 300_000,
                    },
                    policies={"allowlist": manifest.tools, "egress": [], "read_only": True},
                    status="active" if initial else "candidate",
                    created_by=actor_id,
                )
                self.session.add(version)
                await self.session.flush()
                if initial:
                    capability.active_version_id = version.id
                self._audit(
                    actor_id=actor_id,
                    action="agent_registry.version.bootstrap" if initial else "agent_registry.version.candidate",
                    entity_id=version.id,
                    details={"capability": manifest.logical_id, "version": next_version},
                )
            synchronized.append(version)
        await self.session.flush()
        return synchronized

    async def _file_artifact(
        self,
        manifest: CapabilityManifest,
        kind: str,
        source: FileArtifact,
        actor_id: str,
    ) -> AgentArtifact:
        raw = self.loader.read_verified(source)
        content: dict[str, object] = json.loads(raw) if kind == "schema" else {"text": raw.decode("utf-8")}
        return await self._artifact(
            logical_id=f"{manifest.logical_id}.{kind}",
            kind=kind,
            sha256=source.sha256,
            content=content,
            source_path=source.path,
            actor_id=actor_id,
        )

    async def _inline_artifact(
        self,
        manifest: CapabilityManifest,
        kind: str,
        content: dict[str, object],
        actor_id: str,
    ) -> AgentArtifact:
        return await self._artifact(
            logical_id=f"{manifest.logical_id}.{kind}",
            kind=kind,
            sha256=canonical_hash(content),
            content=content,
            source_path=None,
            actor_id=actor_id,
        )

    async def _artifact(
        self,
        *,
        logical_id: str,
        kind: str,
        sha256: str,
        content: dict[str, object],
        source_path: str | None,
        actor_id: str,
    ) -> AgentArtifact:
        existing = (
            await self.session.execute(
                select(AgentArtifact).where(
                    AgentArtifact.logical_id == logical_id,
                    AgentArtifact.kind == kind,
                    AgentArtifact.sha256 == sha256,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        next_version = (
            await self.session.scalar(
                select(func.coalesce(func.max(AgentArtifact.version), 0) + 1).where(
                    AgentArtifact.logical_id == logical_id,
                    AgentArtifact.kind == kind,
                )
            )
        ) or 1
        artifact = AgentArtifact(
            logical_id=logical_id,
            kind=kind,
            version=next_version,
            sha256=sha256,
            content=content,
            source_path=source_path,
            created_by=actor_id,
        )
        self.session.add(artifact)
        await self.session.flush()
        return artifact

    def _audit(self, *, actor_id: str, action: str, entity_id: UUID, details: dict[str, object]) -> None:
        self.session.add(
            AuditLog(
                actor_type="system",
                actor_id=actor_id,
                action=action,
                entity_type="agent_version",
                entity_id=entity_id,
                correlation_id=entity_id,
                details=details,
            )
        )


def default_artifact_loader() -> ArtifactLoader:
    return ArtifactLoader(Path(__file__).resolve().parents[3] / "prompts")


class AgentRuntimeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_run(
        self,
        *,
        organization_id: UUID,
        capability: str,
        case_id: UUID | None,
        input_payload: dict[str, object],
        data_as_of: datetime,
        knowledge_cutoff: datetime,
        actor_id: str,
        permissions: frozenset[str],
        version_pin: UUID | None = None,
        workflow_id: str | None = None,
        trace_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> AgentRuntimeRun:
        if "agent_runs:create" not in permissions:
            raise PermissionError("permission required: agent_runs:create")
        if data_as_of.tzinfo is None or knowledge_cutoff.tzinfo is None:
            raise ValueError("data_as_of and knowledge_cutoff must be timezone-aware")
        if knowledge_cutoff > data_as_of:
            raise ValueError("knowledge_cutoff cannot exceed data_as_of")
        definition = (
            await self.session.execute(select(AgentCapability).where(AgentCapability.logical_id == capability))
        ).scalar_one_or_none()
        if definition is None:
            raise LookupError("agent capability not found")
        input_sha256 = canonical_hash(input_payload)
        if idempotency_key is not None:
            existing = (
                await self.session.execute(
                    select(AgentRuntimeRun).where(
                        AgentRuntimeRun.organization_id == organization_id,
                        AgentRuntimeRun.capability_id == definition.id,
                        AgentRuntimeRun.idempotency_key == idempotency_key,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                if (
                    existing.input_sha256 != input_sha256
                    or existing.case_id != case_id
                    or existing.data_as_of != data_as_of
                    or existing.knowledge_cutoff != knowledge_cutoff
                ):
                    raise ValueError("idempotency key was already used with a different agent run request")
                return existing
        version_id = version_pin or definition.active_version_id
        if version_id is None:
            raise ValueError("agent capability has no active version")
        version = await self.session.get(AgentVersion, version_id)
        if version is None or version.capability_id != definition.id:
            raise ValueError("version pin does not belong to the requested capability")
        if version_pin is None and version.status != "active":
            raise ValueError("active version pointer is inconsistent")
        run = AgentRuntimeRun(
            organization_id=organization_id,
            capability_id=definition.id,
            agent_version_id=version.id,
            case_id=case_id,
            workflow_id=workflow_id,
            trace_id=trace_id or uuid4().hex,
            idempotency_key=idempotency_key,
            input_sha256=input_sha256,
            input_payload=input_payload,
            data_as_of=data_as_of,
            knowledge_cutoff=knowledge_cutoff,
            status="queued",
        )
        self.session.add(run)
        await self.session.flush()
        self._audit(
            actor_type="human",
            actor_id=actor_id,
            action="agent_runtime.run.create",
            entity_type="agent_runtime_run",
            entity_id=run.id,
            correlation_id=run.id,
            details={"capability": capability, "agent_version_id": str(version.id)},
        )
        await self.session.flush()
        return run

    async def request_approval(
        self,
        *,
        run_id: UUID,
        tool_call_id: UUID,
        scope: str,
        impact: dict[str, object],
        requested_by: str,
        expires_at: datetime,
    ) -> AgentApprovalRequest:
        run = await self.session.get(AgentRuntimeRun, run_id, with_for_update=True)
        tool_call = await self.session.get(AgentRuntimeToolCall, tool_call_id)
        if run is None or tool_call is None or tool_call.run_id != run.id:
            raise LookupError("run or tool call not found")
        if run.status not in {"queued", "running"}:
            raise ValueError("run cannot request approval in its current state")
        if expires_at.tzinfo is None or expires_at <= datetime.now(UTC):
            raise ValueError("approval expiry must be an aware future timestamp")
        approval = AgentApprovalRequest(
            run_id=run.id,
            tool_call_id=tool_call.id,
            scope=scope,
            impact=impact,
            requested_by=requested_by,
            expires_at=expires_at,
            status="pending",
        )
        run.status = "awaiting_approval"
        tool_call.status = "requested"
        self.session.add(approval)
        await self.session.flush()
        return approval

    async def start_tool_call(
        self,
        *,
        run_id: UUID,
        tool_name: str,
        tool_version: int,
        arguments: dict[str, object],
    ) -> AgentRuntimeToolCall:
        run = await self.session.get(AgentRuntimeRun, run_id, with_for_update=True)
        if run is None:
            raise LookupError("agent run not found")
        if run.status not in {"queued", "running"}:
            raise ValueError("agent run cannot start a tool call in its current state")
        if tool_version < 1 or not tool_name.strip():
            raise ValueError("tool name and positive version are required")
        sanitized = sanitize_tool_payload(arguments)
        if not isinstance(sanitized, dict):
            raise TypeError("sanitized tool arguments must remain an object")
        call = AgentRuntimeToolCall(
            run_id=run.id,
            tool_name=tool_name,
            tool_version=tool_version,
            arguments_sha256=canonical_hash(arguments),
            sanitized_arguments=sanitized,
            status="requested",
            cost_usd=0,
        )
        run.status = "running"
        self.session.add(call)
        await self.session.flush()
        return call

    async def finish_tool_call(
        self,
        *,
        tool_call_id: UUID,
        status: str,
        result: dict[str, object] | None,
        duration_ms: int,
        cost_usd: Decimal,
    ) -> AgentRuntimeToolCall:
        call = await self.session.get(AgentRuntimeToolCall, tool_call_id, with_for_update=True)
        if call is None:
            raise LookupError("agent tool call not found")
        if call.status not in {"requested", "approved"}:
            raise ValueError("agent tool call was already completed")
        if status not in {"succeeded", "failed", "blocked"}:
            raise ValueError("invalid terminal tool call status")
        if duration_ms < 0 or cost_usd < 0:
            raise ValueError("tool call duration and cost must be nonnegative")
        sanitized_result = sanitize_tool_payload(result) if result is not None else None
        if sanitized_result is not None and not isinstance(sanitized_result, dict):
            raise TypeError("sanitized tool result must remain an object")
        call.status = status
        call.result_payload = sanitized_result
        call.duration_ms = duration_ms
        call.cost_usd = cost_usd
        await self.session.flush()
        return call

    async def decide_approval(
        self,
        *,
        approval_id: UUID,
        decision: str,
        actor_id: str,
        permissions: frozenset[str],
        reason: str,
        correlation_id: UUID,
    ) -> AgentApprovalRequest:
        if "agent_approvals:decide" not in permissions:
            raise PermissionError("permission required: agent_approvals:decide")
        approval = await self.session.get(AgentApprovalRequest, approval_id, with_for_update=True)
        if approval is None:
            raise LookupError("approval request not found")
        if approval.status != "pending":
            raise ValueError("approval request was already decided")
        now = datetime.now(UTC)
        if approval.expires_at <= now:
            approval.status = "expired"
            run = await self.session.get(AgentRuntimeRun, approval.run_id)
            if run is not None:
                run.status = "expired"
            raise ValueError("approval request expired")
        if actor_id == approval.requested_by:
            raise PermissionError("requester cannot approve their own tool call")
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected")
        approval.status = decision
        approval.decided_by = actor_id
        approval.decision_reason = reason
        approval.decided_at = now
        run = await self.session.get(AgentRuntimeRun, approval.run_id, with_for_update=True)
        tool_call = await self.session.get(AgentRuntimeToolCall, approval.tool_call_id, with_for_update=True)
        if run is None or tool_call is None:
            raise RuntimeError("approval references an invalid run or tool call")
        if decision == "approved":
            run.status = "queued"
            tool_call.status = "approved"
        else:
            run.status = "failed"
            run.error_code = "approval_rejected"
            run.error_detail = "A required tool call was rejected"
            run.finished_at = now
            tool_call.status = "blocked"
        self._audit(
            actor_type="human",
            actor_id=actor_id,
            action="agent_runtime.approval.decide",
            entity_type="agent_approval_request",
            entity_id=approval.id,
            correlation_id=correlation_id,
            details={"decision": decision, "reason": reason, "run_id": str(run.id)},
        )
        await self.session.flush()
        return approval

    async def get_run(self, run_id: UUID) -> AgentRuntimeRun | None:
        return await self.session.get(AgentRuntimeRun, run_id)

    async def promote(
        self,
        *,
        capability_id: UUID,
        candidate_version_id: UUID,
        eval_run_id: UUID,
        actor_id: str,
        permissions: frozenset[str],
        override_reason: str | None = None,
        override_expires_at: datetime | None = None,
    ) -> AgentPromotion:
        if "agent_versions:promote" not in permissions:
            raise PermissionError("permission required: agent_versions:promote")
        capability = await self.session.get(AgentCapability, capability_id, with_for_update=True)
        candidate = await self.session.get(AgentVersion, candidate_version_id, with_for_update=True)
        evaluation = await self.session.get(AgentEvalRun, eval_run_id)
        if capability is None or candidate is None or evaluation is None:
            raise LookupError("capability, candidate, or evaluation not found")
        if candidate.capability_id != capability.id or evaluation.candidate_version_id != candidate.id:
            raise ValueError("promotion artifacts do not belong to the same capability/version")
        override = override_reason is not None
        if evaluation.status != "passed" and not override:
            raise ValueError("candidate evaluation did not pass")
        if override:
            if "agent_versions:override" not in permissions:
                raise PermissionError("permission required: agent_versions:override")
            if override_expires_at is None or override_expires_at <= datetime.now(UTC):
                raise ValueError("override requires a future expiry")
        previous_id = capability.active_version_id
        if previous_id is not None:
            previous = await self.session.get(AgentVersion, previous_id, with_for_update=True)
            if previous is not None:
                previous.status = "retired"
        candidate.status = "active"
        capability.active_version_id = candidate.id
        promotion = AgentPromotion(
            capability_id=capability.id,
            from_version_id=previous_id,
            to_version_id=candidate.id,
            eval_run_id=evaluation.id,
            override_reason=override_reason,
            override_expires_at=override_expires_at,
            promoted_by=actor_id,
        )
        self.session.add(promotion)
        await self.session.flush()
        self._audit(
            actor_type="human",
            actor_id=actor_id,
            action="agent_runtime.version.promote",
            entity_type="agent_version",
            entity_id=candidate.id,
            correlation_id=promotion.id,
            details={"from": str(previous_id) if previous_id else None, "override": override},
        )
        await self.session.flush()
        return promotion

    def _audit(
        self,
        *,
        actor_type: str,
        actor_id: str,
        action: str,
        entity_type: str,
        entity_id: UUID,
        correlation_id: UUID,
        details: dict[str, object],
    ) -> None:
        self.session.add(
            AuditLog(
                actor_type=actor_type,
                actor_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                correlation_id=correlation_id,
                details=details,
            )
        )
