from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from temporalio import workflow


@dataclass(frozen=True, slots=True)
class SpecialistResult:
    specialist: str
    verdict: str
    confidence: float
    thesis_effect: str
    key_claims: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ThesisReviewInput:
    thesis_id: str
    thesis_version_id: str
    issuer_id: str
    data_as_of: str
    knowledge_cutoff: str
    specialist_capabilities: tuple[str, ...] = ("filing", "news", "macro", "political", "critic")
    approval_timeout_seconds: int = 86_400


@dataclass(frozen=True, slots=True)
class ThesisReviewResult:
    thesis_id: str
    thesis_version_id: str
    status: str
    specialist_results: tuple[SpecialistResult, ...]
    contradictions_found: tuple[str, ...]
    diff_hash: str
    decision: str
    approved_by: str | None = None


@workflow.defn
class ThesisReviewWorkflow:
    """Orchestrates a full thesis review: load context, run specialists, detect contradictions,
    generate diff, pause for human approval, and activate/reject the version.

    This workflow NEVER mutates a thesis directly. It collects evidence and recommendations,
    then pauses for human approval. The actual activation happens through ThesisService.activate()
    called by the API after the human approves.
    """

    def __init__(self) -> None:
        self._decision: str | None = None
        self._reviewer: str = ""
        self._specialist_results: list[SpecialistResult] = []

    @workflow.run
    async def run(self, command: ThesisReviewInput) -> ThesisReviewResult:
        if command.approval_timeout_seconds <= 0:
            raise ValueError("approval_timeout_seconds must be positive")

        # Step 1: Load active thesis version and valid facts/evidence at cutoff
        thesis_context = await workflow.execute_activity(
            "load_thesis_context",
            args=[command.thesis_id, command.data_as_of, command.knowledge_cutoff],
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Step 2: Run specialist mock activities with fixed versions
        specialist_results: list[SpecialistResult] = []
        for capability in command.specialist_capabilities:
            result = await workflow.execute_activity(
                f"run_specialist_{capability}",
                args=[
                    command.issuer_id,
                    thesis_context,
                    command.data_as_of,
                    command.knowledge_cutoff,
                ],
                start_to_close_timeout=timedelta(seconds=60),
            )
            specialist_results.append(
                SpecialistResult(
                    specialist=capability,
                    verdict=result.get("verdict", "neutral"),
                    confidence=result.get("confidence", 0.0),
                    thesis_effect=result.get("thesis_effect", "no_change"),
                    key_claims=result.get("key_claims", []),
                    risks=result.get("risks", []),
                    contradictions=result.get("contradictions", []),
                )
            )

        self._specialist_results = specialist_results

        # Step 3: Detect contradictions across specialist outputs
        contradictions = self._detect_contradictions(specialist_results)

        # Step 4: Generate diff hash for the thesis version
        diff_hash = self._compute_diff_hash(command.thesis_version_id, thesis_context, specialist_results)

        # Step 5: Pause for human approval
        try:
            await workflow.wait_condition(
                lambda: self._decision is not None,
                timeout=timedelta(seconds=command.approval_timeout_seconds),
            )
        except TimeoutError:
            self._decision = "expired"

        decision = self._decision or "expired"

        return ThesisReviewResult(
            thesis_id=command.thesis_id,
            thesis_version_id=command.thesis_version_id,
            status=decision,
            specialist_results=tuple(specialist_results),
            contradictions_found=tuple(contradictions),
            diff_hash=diff_hash,
            decision=decision,
            approved_by=self._reviewer or None,
        )

    @workflow.signal
    async def approve(self, reviewer: str) -> None:
        if self._decision is None:
            self._decision = "approved"
            self._reviewer = reviewer

    @workflow.signal
    async def reject(self, reviewer: str, reason: str = "") -> None:
        if self._decision is None:
            self._decision = "rejected"
            self._reviewer = reviewer

    @workflow.signal
    async def cancel(self) -> None:
        if self._decision is None:
            self._decision = "cancelled"

    @workflow.query
    def state(self) -> str:
        if self._decision is not None:
            return self._decision
        if self._specialist_results:
            return "awaiting_approval"
        return "running"

    @workflow.query
    def specialist_results(self) -> list[SpecialistResult]:
        return list(self._specialist_results)

    def _detect_contradictions(self, results: list[SpecialistResult]) -> list[str]:
        contradictions: list[str] = []
        effects = [r.thesis_effect for r in results if r.thesis_effect != "no_change"]
        if "strengthen" in effects and "weaken" in effects:
            contradictions.append("specialists_disagree_on_direction")
        for r in results:
            contradictions.extend(r.contradictions)
        return contradictions

    def _compute_diff_hash(
        self,
        version_id: str,
        thesis_context: dict[str, Any],
        specialist_results: list[SpecialistResult],
    ) -> str:
        payload = {
            "version_id": version_id,
            "context_hash": thesis_context.get("content_sha256", ""),
            "specialist_verdicts": [
                {"specialist": r.specialist, "effect": r.thesis_effect, "confidence": r.confidence}
                for r in specialist_results
            ],
        }
        canonical = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()
