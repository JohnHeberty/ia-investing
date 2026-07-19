from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ArtifactIntegrityError(RuntimeError):
    pass


class FileArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ModelProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    temperature: float = Field(ge=0, le=2)


class CapabilityManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logical_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    prompt: FileArtifact
    schema_: FileArtifact = Field(alias="schema")
    model_profile: ModelProfile
    tools: list[str]


class AgentRegistryManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registry_version: int = Field(gt=0)
    capabilities: list[CapabilityManifest]


class ArtifactLoader:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def resolve(self, relative_path: str) -> Path:
        candidate = Path(relative_path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ArtifactIntegrityError(f"Artifact path is not safe: {relative_path}")
        resolved = (self.root / candidate).resolve()
        if not resolved.is_relative_to(self.root):
            raise ArtifactIntegrityError(f"Artifact path escapes registry root: {relative_path}")
        return resolved

    def read_verified(self, artifact: FileArtifact) -> bytes:
        path = self.resolve(artifact.path)
        try:
            content = path.read_bytes()
        except FileNotFoundError as exc:
            raise ArtifactIntegrityError(f"Registered artifact is missing: {artifact.path}") from exc
        actual = hashlib.sha256(content).hexdigest()
        if actual != artifact.sha256:
            raise ArtifactIntegrityError(f"Registered artifact hash mismatch: {artifact.path}")
        return content

    def load_registry(self, path: str = "registry.json") -> AgentRegistryManifest:
        registry_path = self.resolve(path)
        try:
            raw = json.loads(registry_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            raise ArtifactIntegrityError("Agent registry is missing or invalid") from exc
        registry = AgentRegistryManifest.model_validate(raw)
        logical_ids = [item.logical_id for item in registry.capabilities]
        if len(logical_ids) != len(set(logical_ids)):
            raise ArtifactIntegrityError("Agent registry contains duplicate capability IDs")
        for capability in registry.capabilities:
            self.read_verified(capability.prompt)
            schema_bytes = self.read_verified(capability.schema_)
            try:
                json.loads(schema_bytes)
            except json.JSONDecodeError as exc:
                raise ArtifactIntegrityError(f"Output schema is invalid: {capability.schema_.path}") from exc
        return registry
