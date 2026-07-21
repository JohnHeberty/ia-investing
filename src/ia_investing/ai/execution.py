from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from opentelemetry import trace
from opentelemetry.metrics import get_meter
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.agent_runtime import AgentArtifact, AgentCapability, AgentRuntimeRun, AgentVersion
from database.models.research import ResearchEvidence

from .contracts import CoordinatorOutput
from .guardrails import (
    BudgetUsage,
    GuardrailViolationError,
    RunBudget,
    enforce_budget,
    validate_specialist_output,
    validate_untrusted_text,
)
from .provider import AgentProvider, ProviderError
from .tracing import inject_traceparent_into_context

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("ia_investing.agent_runtime")
meter = get_meter("ia_investing.agent_runtime")
run_counter = meter.create_counter("agent.runtime.runs", unit="{run}")
token_counter = meter.create_counter("agent.runtime.tokens", unit="{token}")
cost_histogram = meter.create_histogram("agent.runtime.cost", unit="USD")
duration_histogram = meter.create_histogram("agent.runtime.duration", unit="ms")
schema_pass_counter = meter.create_counter("agent.runtime.schema_pass", unit="{output}")
citation_coverage_histogram = meter.create_histogram("agent.runtime.citation_coverage", unit="1")
guardrail_trip_counter = meter.create_counter("agent.runtime.guardrail_trips", unit="{trip}")


class AgentExecutionService:
    def __init__(self, session: AsyncSession, provider: AgentProvider) -> None:
        self.session = session
        self.provider = provider

    async def execute(self, run_id: UUID) -> AgentRuntimeRun:
        run = await self.session.get(AgentRuntimeRun, run_id, with_for_update=True)
        if run is None:
            raise LookupError("agent run not found")
        if run.status not in {"queued", "running"}:
            raise ValueError("agent run cannot execute in its current state")
        version = await self.session.get(AgentVersion, run.agent_version_id)
        capability = await self.session.get(AgentCapability, run.capability_id)
        if version is None or capability is None or version.capability_id != capability.id:
            raise RuntimeError("run references an inconsistent agent version")
        artifacts = {
            artifact.id: artifact
            for artifact in (
                await self.session.execute(
                    sa.select(AgentArtifact).where(
                        AgentArtifact.id.in_(
                            {
                                version.prompt_artifact_id,
                                version.schema_artifact_id,
                                version.model_artifact_id,
                                version.toolset_artifact_id,
                            }
                        )
                    )
                )
            ).scalars()
        }
        if len(artifacts) != 4:
            return await self._fail(run, "artifact_missing", "A pinned runtime artifact is missing")
        prompt = artifacts[version.prompt_artifact_id]
        schema = artifacts[version.schema_artifact_id]
        model = artifacts[version.model_artifact_id]
        if prompt.kind != "prompt" or schema.kind != "schema" or model.kind != "model_profile":
            return await self._fail(run, "artifact_kind_mismatch", "A pinned runtime artifact has the wrong kind")
        instructions = prompt.content.get("text")
        model_name = model.content.get("model")
        if not isinstance(instructions, str) or not isinstance(model_name, str):
            return await self._fail(run, "artifact_invalid", "A pinned runtime artifact is invalid")

        run.status = "running"
        run.started_at = datetime.now(UTC)
        await self.session.flush()
        span_attributes = {
            "agent.run_id": str(run.id),
            "agent.capability": capability.logical_id,
            "agent.version": version.version,
            "agent.case_id": str(run.case_id) if run.case_id else "",
            "agent.workflow_id": run.workflow_id or "",
            "agent.trace_id": run.trace_id,
            "agent.prompt_hash": prompt.sha256,
            "agent.schema_hash": schema.sha256,
        }
        try:
            parent_ctx = inject_traceparent_into_context(run.trace_id) if run.trace_id else None
            with tracer.start_as_current_span(
                "agent.execute",
                attributes=span_attributes,
                context=parent_ctx,
            ) as span:
                validate_untrusted_text(str(run.input_payload))
                with tracer.start_as_current_span("provider.complete") as provider_span:
                    response = await self.provider.complete(
                        model=model_name,
                        instructions=instructions,
                        input_payload=run.input_payload,
                        output_schema=schema.content,
                    )
                provider_span.set_attributes(
                    {
                        "provider.model": model_name,
                        "provider.run_id": response.provider_run_id or "",
                        "provider.prompt_tokens": response.usage.prompt_tokens,
                        "provider.completion_tokens": response.usage.completion_tokens,
                    }
                )
                usage = BudgetUsage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    cost_usd=response.usage.cost_usd,
                    turns=1,
                    duration_ms=response.usage.duration_ms,
                )
                enforce_budget(RunBudget.model_validate(version.budgets), usage)
                output = await self._validate_output(capability.logical_id, run, response.output)
                span.set_attributes(
                    {
                        "agent.model": model_name,
                        "agent.prompt_tokens": response.usage.prompt_tokens,
                        "agent.completion_tokens": response.usage.completion_tokens,
                        "agent.cost_usd": float(response.usage.cost_usd),
                        "agent.duration_ms": response.usage.duration_ms,
                        "agent.schema_pass": True,
                        "agent.citation_coverage": 1.0,
                    }
                )
        except GuardrailViolationError as exc:
            return await self._fail(run, exc.code, str(exc), guardrail=True)
        except ProviderError as exc:
            return await self._fail(run, exc.code, exc.safe_detail)

        run.output_payload = output
        run.provider_run_id = response.provider_run_id
        run.prompt_tokens = response.usage.prompt_tokens
        run.completion_tokens = response.usage.completion_tokens
        run.cost_usd = response.usage.cost_usd
        run.duration_ms = response.usage.duration_ms
        run.evidence_coverage = Decimal(1)
        run.status = "succeeded"
        run.finished_at = datetime.now(UTC)
        await self.session.flush()
        attributes = {
            "agent.capability": capability.logical_id,
            "agent.version": str(version.version),
            "agent.model": model_name,
            "agent.status": "succeeded",
        }
        run_counter.add(1, attributes)
        token_counter.add(run.prompt_tokens, {**attributes, "agent.token_type": "prompt"})
        token_counter.add(run.completion_tokens, {**attributes, "agent.token_type": "completion"})
        cost_histogram.record(float(run.cost_usd), attributes)
        duration_histogram.record(run.duration_ms or 0, attributes)
        schema_pass_counter.add(1, attributes)
        citation_coverage_histogram.record(float(run.evidence_coverage), attributes)
        logger.info(
            "agent run succeeded run_id=%s capability=%s version=%s tokens=%s/%s cost_usd=%s duration_ms=%s",
            run.id,
            capability.logical_id,
            version.version,
            run.prompt_tokens,
            run.completion_tokens,
            run.cost_usd,
            run.duration_ms,
        )
        return run

    async def _validate_output(
        self,
        capability: str,
        run: AgentRuntimeRun,
        payload: dict[str, object],
    ) -> dict[str, object]:
        if capability == "research_coordinator":
            return CoordinatorOutput.model_validate(payload).model_dump(mode="json")
        if capability not in {"filing", "news", "macro", "political", "critic"}:
            raise GuardrailViolationError("unsupported_capability", "Capability has no output validator")
        evidence_ids: set[UUID] = set()
        if run.case_id is not None:
            evidence_ids = set(
                (
                    await self.session.execute(
                        sa.select(ResearchEvidence.id).where(
                            ResearchEvidence.research_case_id == run.case_id,
                            ResearchEvidence.knowledge_at <= run.knowledge_cutoff,
                            ResearchEvidence.revoked_at.is_(None),
                            sa.or_(
                                ResearchEvidence.valid_until.is_(None),
                                ResearchEvidence.valid_until > run.knowledge_cutoff,
                            ),
                        )
                    )
                ).scalars()
            )
        output = validate_specialist_output(
            payload,
            allowed_evidence_ids=evidence_ids,
            expected_cutoff=run.knowledge_cutoff,
        )
        if output.capability != capability:
            raise GuardrailViolationError("capability_mismatch", "Output capability does not match pinned run")
        return output.model_dump(mode="json")

    async def _fail(
        self,
        run: AgentRuntimeRun,
        code: str,
        safe_detail: str,
        *,
        guardrail: bool = False,
    ) -> AgentRuntimeRun:
        run.status = "failed"
        run.error_code = code
        run.error_detail = safe_detail[:2_000]
        run.finished_at = datetime.now(UTC)
        await self.session.flush()
        attributes = {"agent.status": "failed", "agent.error_code": code}
        run_counter.add(1, attributes)
        if guardrail:
            guardrail_trip_counter.add(1, attributes)
        logger.warning("agent run failed run_id=%s code=%s", run.id, code)
        return run
