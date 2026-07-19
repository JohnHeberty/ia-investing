from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select

from database.core import session_scope
from database.models.agent_runtime import AgentArtifact, AgentCapability, AgentRuntimeToolCall, AgentVersion
from ia_investing.ai.artifacts import ArtifactLoader
from ia_investing.ai.execution import AgentExecutionService
from ia_investing.ai.provider import MockProvider
from ia_investing.application.agent_runtime import AgentRegistryService, AgentRuntimeService, canonical_hash


async def verify() -> None:
    loader = ArtifactLoader(Path("prompts"))
    async with session_scope() as session:
        registry = AgentRegistryService(session, loader)
        first = await registry.synchronize("verify-agent-runtime")
        artifact_count = await session.scalar(select(func.count()).select_from(AgentArtifact))
        second = await registry.synchronize("verify-agent-runtime")
        assert [item.id for item in first] == [item.id for item in second]
        assert artifact_count == await session.scalar(select(func.count()).select_from(AgentArtifact))

        capability = (
            await session.execute(select(AgentCapability).where(AgentCapability.logical_id == "filing"))
        ).scalar_one()
        version = await session.get(AgentVersion, capability.active_version_id)
        assert version is not None and version.status == "active"

        now = datetime.now(UTC)
        service = AgentRuntimeService(session)
        run = await service.create_run(
            capability="filing",
            case_id=None,
            input_payload={"question": "validate runtime"},
            data_as_of=now,
            knowledge_cutoff=now - timedelta(minutes=1),
            actor_id="runtime-author",
            permissions=frozenset({"agent_runs:create"}),
        )
        assert run.agent_version_id == version.id
        tool_call = AgentRuntimeToolCall(
            run_id=run.id,
            tool_name="request_thesis_update",
            tool_version=1,
            arguments_sha256=canonical_hash({"case": "verify"}),
            sanitized_arguments={"case": "verify"},
            status="requested",
            cost_usd=Decimal(0),
        )
        session.add(tool_call)
        await session.flush()
        approval = await service.request_approval(
            run_id=run.id,
            tool_call_id=tool_call.id,
            scope="research_case:verify",
            impact={"operation": "request_thesis_update"},
            requested_by="runtime-author",
            expires_at=now + timedelta(minutes=10),
        )
        pinned_version_id = run.agent_version_id
        await service.decide_approval(
            approval_id=approval.id,
            decision="approved",
            actor_id="independent-reviewer",
            permissions=frozenset({"agent_approvals:decide"}),
            reason="verified four-eyes resume",
            correlation_id=uuid4(),
        )
        try:
            await service.decide_approval(
                approval_id=approval.id,
                decision="rejected",
                actor_id="another-reviewer",
                permissions=frozenset({"agent_approvals:decide"}),
                reason="duplicate must fail",
                correlation_id=uuid4(),
            )
        except ValueError as exc:
            assert "already decided" in str(exc)
        else:
            raise AssertionError("duplicate approval decision was accepted")
        assert run.status == "queued"
        assert run.agent_version_id == pinned_version_id
        prompt = await session.get(AgentArtifact, version.prompt_artifact_id)
        model = await session.get(AgentArtifact, version.model_artifact_id)
        assert prompt is not None and model is not None
        instructions = prompt.content["text"]
        model_name = model.content["model"]
        assert isinstance(instructions, str) and isinstance(model_name, str)
        key = MockProvider.request_key(model_name, instructions, run.input_payload)
        provider = MockProvider(
            {
                key: {
                    "capability": "filing",
                    "summary": "Runtime verification",
                    "findings": [],
                    "contradictions": [],
                    "uncertainty": [],
                    "materiality": "low",
                    "knowledge_cutoff": run.knowledge_cutoff.isoformat(),
                }
            }
        )
        await AgentExecutionService(session, provider).execute(run.id)
        assert run.status == "succeeded"
        assert run.output_payload is not None
        print(
            "agent-runtime-ok",
            f"capabilities={len(first)}",
            f"artifacts={artifact_count}",
            "idempotent=true",
            "four_eyes=true",
            "version_pinned=true",
            "structured_output=true",
            "duplicate_decision_blocked=true",
        )


if __name__ == "__main__":
    asyncio.run(verify())
