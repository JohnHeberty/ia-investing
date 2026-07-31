"""Synchronous candidate analysis pipeline — runs all 10 stages
without Temporal orchestration. Calls ProductionCandidateRuntime
methods directly in sequence.

Usage:
    result = await run_candidate_pipeline(candidate_id, organization_id)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from ia_investing.integrations.production_runtime import ProductionCandidateRuntime
from ia_investing.orchestration.activities.candidate_intelligence import (
    CandidateCheckpoint,
    CandidateWorkflowInput,
    SourceDiscoveryCheckpoint,
)
from ia_investing.platform.database.runtime import DatabaseRuntime

logger = logging.getLogger(__name__)


@dataclass
class StageResult:
    stage: str
    status: str
    reason: str
    blocker_codes: list[str]
    duration_ms: float
    payload: dict[str, Any] | None = None


@dataclass
class PipelineResult:
    candidate_id: UUID
    run_id: UUID
    final_status: str
    stages: list[StageResult] = field(default_factory=list)
    total_duration_ms: float = 0.0


async def _update_candidate_status(
    db: DatabaseRuntime,
    candidate_id: UUID,
    new_status: str,
) -> None:
    from database.models.investment_candidates import InvestmentCandidateRecord
    import sqlalchemy as sa

    async with db.session() as session:
        candidate = (
            await session.execute(
                sa.select(InvestmentCandidateRecord).where(
                    InvestmentCandidateRecord.id == candidate_id,
                )
            )
        ).scalars().one_or_none()
        if candidate is not None:
            candidate.status = new_status
            candidate.lock_version += 1
            await session.commit()


def _make_blocked(stage: str, reason: str) -> CandidateCheckpoint:
    return CandidateCheckpoint(
        candidate_id=UUID(int=0),
        stage=stage,
        blocked=True,
        decision="blocked",
        reason=reason,
        blocker_codes=(f"{stage}_blocked",),
    )


async def _record_event(
    db: DatabaseRuntime,
    candidate_id: UUID,
    organization_id: UUID,
    stage_name: str,
    checkpoint: CandidateCheckpoint,
) -> None:
    from database.models.investment_candidates import CandidateEventRecord, InvestmentCandidateRecord
    import sqlalchemy as sa

    async with db.session() as session:
        candidate = (
            await session.execute(
                sa.select(InvestmentCandidateRecord).where(
                    InvestmentCandidateRecord.id == candidate_id,
                )
            )
        ).scalars().one_or_none()
        current_version = (candidate.lock_version if candidate else 0) + 1

        session.add(
            CandidateEventRecord(
                candidate_id=candidate_id,
                organization_id=organization_id,
                event_type=f"pipeline_{stage_name}",
                actor_type="system",
                actor_id="sync_pipeline",
                occurred_at=datetime.now(UTC),
                aggregate_version=current_version,
                payload={
                    "stage": checkpoint.stage,
                    "blocked": checkpoint.blocked,
                    "reason": checkpoint.reason,
                    "blocker_codes": list(checkpoint.blocker_codes),
                    "decision": checkpoint.decision,
                },
            )
        )
        try:
            await session.commit()
        except Exception:
            await session.rollback()
            logger.debug("Could not record pipeline event %s (version collision)", stage_name)


async def run_candidate_pipeline(
    candidate_id: UUID,
    organization_id: UUID,
    *,
    skip_stages: list[str] | None = None,
) -> PipelineResult:
    skip = set(skip_stages or [])
    pipeline_start = time.monotonic()
    stages_result: list[StageResult] = []

    db = DatabaseRuntime.create(
        _get_database_url(),
    )

    from database.models.investment_candidates import (
        CandidateAnalysisRunRecord,
        InvestmentCandidateRecord,
    )
    import sqlalchemy as sa

    async with db.session() as session:
        candidate = (
            await session.execute(
                sa.select(InvestmentCandidateRecord).where(
                    InvestmentCandidateRecord.id == candidate_id,
                )
            )
        ).scalars().one_or_none()
        if candidate is None:
            return PipelineResult(
                candidate_id=candidate_id,
                run_id=UUID(int=0),
                final_status="failed",
                stages=[],
                total_duration_ms=0,
            )
        org_id = candidate.organization_id

        run = (
            await session.execute(
                sa.select(CandidateAnalysisRunRecord).where(
                    CandidateAnalysisRunRecord.candidate_id == candidate_id,
                ).order_by(CandidateAnalysisRunRecord.run_number.desc()).limit(1)
            )
        ).scalars().one_or_none()
        if run is None:
            run = CandidateAnalysisRunRecord(
                candidate_id=candidate_id,
                run_number=1,
                trigger="manual_pipeline",
                status="running",
                requested_by="sync_pipeline",
                requested_at=datetime.now(UTC),
                data_as_of=datetime.now(UTC),
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
        else:
            run.status = "running"
            run.started_at = datetime.now(UTC)
            await session.commit()

    from ia_investing.platform.http.safe_client import EgressPolicy, SafeHttpClient

    http_client = SafeHttpClient(policy=EgressPolicy())
    runtime = ProductionCandidateRuntime(
        db=db,
        http_client=http_client,
        object_store=None,
    )

    command = CandidateWorkflowInput(
        candidate_id=candidate_id,
        analysis_run_id=run.id,
        organization_id=org_id,
        data_as_of=datetime.now(UTC),
    )

    last_checkpoint: CandidateCheckpoint | None = None
    current_status = candidate.status

    async def _run_stage(
        name: str,
        method: Any,
        new_status: str | None,
        transform: Any = None,
        allow_persist_duplicate: bool = False,
    ) -> CandidateCheckpoint:
        nonlocal current_status

        if name in skip:
            return CandidateCheckpoint(
                candidate_id=candidate_id,
                stage=name,
                blocked=False,
                decision="skipped",
                reason=f"Skipped by request",
            )

        if new_status and new_status != current_status:
            await _update_candidate_status(db, candidate_id, new_status)
            current_status = new_status

        t0 = time.monotonic()
        try:
            if transform:
                result = await method(transform)
            else:
                result = await method(command)
        except Exception as exc:
            is_duplicate = "UniqueViolation" in str(type(exc).__name__) or "unique constraint" in str(exc).lower()
            if is_duplicate and allow_persist_duplicate:
                logger.info("Pipeline stage %s: duplicate sources (already persisted), continuing", name)
                result = CandidateCheckpoint(
                    candidate_id=candidate_id,
                    stage=name,
                    blocked=False,
                    decision="completed",
                    reason=f"{name} completed (sources already persisted)",
                )
            else:
                logger.exception("Pipeline stage %s failed with exception", name)
                result = CandidateCheckpoint(
                    candidate_id=candidate_id,
                    stage=name,
                    blocked=True,
                    decision="failed",
                    reason=f"Exception: {exc}",
                    blocker_codes=(f"{name}_exception",),
                )

        if result is None:
            result = CandidateCheckpoint(
                candidate_id=candidate_id,
                stage=name,
                blocked=False,
                decision="completed",
                reason=f"{name} completed (no checkpoint returned)",
            )
        checkpoint = result
        duration = (time.monotonic() - t0) * 1000

        if hasattr(checkpoint, "stage"):
            await _record_event(db, candidate_id, org_id, name, checkpoint)

            stages_result.append(StageResult(
                stage=name,
                status="blocked" if checkpoint.blocked else "passed",
                reason=checkpoint.reason,
                blocker_codes=list(checkpoint.blocker_codes),
                duration_ms=round(duration, 1),
                payload=checkpoint.payload,
            ))
        else:
            stages_result.append(StageResult(
                stage=name,
                status="passed",
                reason=f"{name} completed",
                blocker_codes=[],
                duration_ms=round(duration, 1),
            ))

        logger.info(
            "Pipeline %s stage=%s status=%s reason=%s (%.0fms)",
            candidate_id, name,
            "blocked" if hasattr(checkpoint, "blocked") and checkpoint.blocked else "passed",
            getattr(checkpoint, "reason", "ok"),
            duration,
        )
        return checkpoint

    async def _run_stage_source_discovery(
        name: str,
        method: Any,
        new_status: str | None,
    ) -> dict[str, Any] | None:
        nonlocal current_status

        if name in skip:
            return None

        if new_status and new_status != current_status:
            await _update_candidate_status(db, candidate_id, new_status)
            current_status = new_status

        t0 = time.monotonic()
        try:
            raw = await method(command)
        except Exception as exc:
            logger.exception("Pipeline stage %s failed", name)
            duration = (time.monotonic() - t0) * 1000
            stages_result.append(StageResult(
                stage=name, status="blocked",
                reason=f"Exception: {exc}",
                blocker_codes=[f"{name}_exception"],
                duration_ms=round(duration, 1),
            ))
            return None

        duration = (time.monotonic() - t0) * 1000
        output = raw.output if hasattr(raw, "output") else {}
        stages_result.append(StageResult(
            stage=name,
            status="passed",
            reason=f"Discovery complete: {len(output.get('sources', []))} sources found",
            blocker_codes=[],
            duration_ms=round(duration, 1),
        ))
        return {"blocked": False, "raw": raw, "reason": "ok"}

    # --- Stage 1: Identity Resolution ---
    checkpoint = await _run_stage(
        "identity_resolution",
        runtime.resolve_candidate_identity,
        "identity_resolution",
    )
    if checkpoint.blocked:
        last_checkpoint = checkpoint
    else:
        # --- Stage 2: Source Discovery ---
        source_checkpoint = await _run_stage_source_discovery(
            "source_discovery",
            runtime.discover_candidate_sources,
            "source_discovery",
        )
        if source_checkpoint is None:
            last_checkpoint = _make_blocked("source_discovery", "Source discovery returned None")
        elif not source_checkpoint.get("blocked", False):
            # --- Stage 2b: Persist Sources ---
            persist_checkpoint = await _run_stage(
                "source_persist",
                runtime.persist_candidate_sources_and_gaps,
                None,
                transform=source_checkpoint["raw"],
                allow_persist_duplicate=True,
            )

            # --- Stage 2c: Validate each discovered source ---
            from database.models.investment_candidates import CandidateSourceRecord
            import sqlalchemy as sa

            async with db.session() as session:
                unverified_sources = (
                    await session.execute(
                        sa.select(CandidateSourceRecord).where(
                            CandidateSourceRecord.candidate_id == candidate_id,
                            CandidateSourceRecord.status == "discovered",
                        )
                    )
                ).scalars().all()

            if unverified_sources:
                from ia_investing.orchestration.activities.candidate_intelligence import CandidateSourceValidationInput

                validated_count = 0
                for src in unverified_sources:
                    val_input = CandidateSourceValidationInput(
                        candidate_id=candidate_id,
                        source_id=src.id,
                        organization_id=org_id,
                    )
                    try:
                        val_result = await runtime.validate_supplied_candidate_source(val_input)
                        validated_count += 1
                        logger.info("Validated source %s (%s): %s", src.id, src.kind, val_result.status)
                    except Exception as exc:
                        logger.warning("Failed to validate source %s: %s", src.id, exc)

                stages_result.append(StageResult(
                    stage="source_individual_validation",
                    status="passed",
                    reason=f"Validated {validated_count}/{len(unverified_sources)} sources",
                    blocker_codes=[],
                    duration_ms=0,
                ))

            # --- Stage 3: Source Validation (bulk check) ---
            val_checkpoint = await _run_stage(
                "source_validation",
                runtime.validate_candidate_sources,
                "source_validation",
            )
            if val_checkpoint.blocked:
                last_checkpoint = val_checkpoint
            else:
                # --- Stage 3b: Readiness Check ---
                ready_checkpoint = await _run_stage(
                    "readiness",
                    runtime.evaluate_candidate_readiness,
                    None,
                )
                if ready_checkpoint.blocked:
                    last_checkpoint = ready_checkpoint
                else:
                    # --- Stage 4: Document Collection ---
                    doc_checkpoint = await _run_stage(
                        "document_collection",
                        runtime.collect_candidate_documents,
                        "document_collection",
                    )
                    if doc_checkpoint.blocked:
                        last_checkpoint = doc_checkpoint
                    else:
                        # --- Stage 4b: Financial Data Ingestion ---
                        fin_checkpoint = await _run_stage(
                            "financial_ingestion",
                            runtime.ingest_candidate_financial_data,
                            "data_quality",
                        )
                        if fin_checkpoint.blocked:
                            last_checkpoint = fin_checkpoint
                        else:
                            # --- Stage 5: Data Quality Validation ---
                            dq_checkpoint = await _run_stage(
                                "data_quality",
                                runtime.validate_candidate_financial_data,
                                "data_quality",
                            )
                            if dq_checkpoint.blocked:
                                last_checkpoint = dq_checkpoint
                            else:
                                # --- Stage 6: Fundamental Analysis ---
                                fund_checkpoint = await _run_stage(
                                    "fundamental_analysis",
                                    runtime.run_candidate_fundamental_analysis,
                                    "fundamental_analysis",
                                )
                                if fund_checkpoint.blocked:
                                    last_checkpoint = fund_checkpoint
                                else:
                                    # --- Stage 7: Risk Analysis ---
                                    risk_checkpoint = await _run_stage(
                                        "risk_analysis",
                                        runtime.run_candidate_risk_analysis,
                                        "risk_analysis",
                                    )
                                    if risk_checkpoint.blocked:
                                        last_checkpoint = risk_checkpoint
                                    else:
                                        # --- Stage 8: Committee Pack ---
                                        committee_checkpoint = await _run_stage(
                                            "committee_review",
                                            runtime.create_committee_pack,
                                            "committee_review",
                                        )
                                        last_checkpoint = committee_checkpoint
        else:
            last_checkpoint = _make_blocked("source_discovery", source_checkpoint.get("reason", "blocked"))

    # --- Finalize ---
    if last_checkpoint is None:
        last_checkpoint = CandidateCheckpoint(
            candidate_id=candidate_id,
            stage="unknown",
            blocked=True,
            decision="failed",
            reason="No checkpoint recorded",
            blocker_codes=("pipeline_error",),
        )

    try:
        workflow_result = await runtime.complete_candidate_analysis_run(
            command, last_checkpoint,
        )
        final_status = workflow_result.status
    except Exception as exc:
        logger.exception("Failed to complete pipeline run for %s", candidate_id)
        final_status = "failed"

    total_ms = (time.monotonic() - pipeline_start) * 1000

    return PipelineResult(
        candidate_id=candidate_id,
        run_id=run.id,
        final_status=final_status,
        stages=stages_result,
        total_duration_ms=round(total_ms, 1),
    )


def _get_database_url() -> str:
    from ia_investing.settings import get_settings
    settings = get_settings()
    return str(settings.database.url)
