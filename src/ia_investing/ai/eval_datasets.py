from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

REQUIRED_CAPABILITIES = frozenset({"filing", "news", "macro", "political", "critic", "research_coordinator"})
REQUIRED_ADVERSARIAL_TAGS = frozenset({"prompt_injection", "conflicting_evidence", "future_date"})


class EvalCaseFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1)
    tags: list[str] = Field(min_length=1)
    input: dict[str, object]
    expected: dict[str, object]


class EvalDatasetFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(gt=0)
    capabilities: dict[str, list[EvalCaseFile]]


def load_eval_dataset(path: Path) -> tuple[EvalDatasetFile, str]:
    raw = path.read_bytes()
    dataset = EvalDatasetFile.model_validate_json(raw)
    capabilities = set(dataset.capabilities)
    if capabilities != REQUIRED_CAPABILITIES:
        raise ValueError(f"eval capabilities mismatch: {sorted(capabilities ^ REQUIRED_CAPABILITIES)}")
    all_tags: set[str] = set()
    for capability, cases in dataset.capabilities.items():
        if not cases:
            raise ValueError(f"eval capability has no cases: {capability}")
        keys = [case.key for case in cases]
        if len(keys) != len(set(keys)):
            raise ValueError(f"eval case keys are duplicated: {capability}")
        all_tags.update(tag for case in cases for tag in case.tags)
    missing_tags = REQUIRED_ADVERSARIAL_TAGS - all_tags
    if missing_tags:
        raise ValueError(f"eval dataset lacks adversarial tags: {sorted(missing_tags)}")
    canonical = json.dumps(dataset.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return dataset, hashlib.sha256(canonical.encode()).hexdigest()
