from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.agent_runtime import (
    AgentArtifact,
    AgentCapability,
    AgentVersion,
)
from database.models.agents import AuditLog
from ia_investing.ai.artifacts import ArtifactLoader, CapabilityManifest, FileArtifact
from ia_investing.application.agent_runtime._crypto import canonical_hash


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
    return ArtifactLoader(Path(__file__).resolve().parents[4] / "prompts")
