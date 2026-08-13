"""Synchronous candidate analysis pipeline.

Runs all 10 stages without Temporal orchestration. Calls ProductionCandidateRuntime
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
    import sqlalchemy as sa

    from database.models.investment_candidates import InvestmentCandidateRecord

    async with db.session() as session:
        candidate = (
            (
                await session.execute(
                    sa.select(InvestmentCandidateRecord).where(
                        InvestmentCandidateRecord.id == candidate_id,
                    )
                )
            )
            .scalars()
            .one_or_none()
        )
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
    import sqlalchemy as sa

    from database.models.investment_candidates import CandidateEventRecord, InvestmentCandidateRecord

    async with db.session() as session:
        candidate = (
            (
                await session.execute(
                    sa.select(InvestmentCandidateRecord).where(
                        InvestmentCandidateRecord.id == candidate_id,
                    )
                )
            )
            .scalars()
            .one_or_none()
        )
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

    import sqlalchemy as sa

    from database.models.investment_candidates import (
        CandidateAnalysisRunRecord,
        CandidateGapRecord,
        CandidateSourceRecord,
        InvestmentCandidateRecord,
    )

    db = DatabaseRuntime.create(
        _get_database_url(),
    )

    async with db.session() as session:
        candidate = (
            (
                await session.execute(
                    sa.select(InvestmentCandidateRecord).where(
                        InvestmentCandidateRecord.id == candidate_id,
                    )
                )
            )
            .scalars()
            .one_or_none()
        )
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
            (
                await session.execute(
                    sa.select(CandidateAnalysisRunRecord)
                    .where(
                        CandidateAnalysisRunRecord.candidate_id == candidate_id,
                    )
                    .order_by(CandidateAnalysisRunRecord.run_number.desc())
                    .limit(1)
                )
            )
            .scalars()
            .one_or_none()
        )
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
                reason="Skipped by request",
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

        if not isinstance(result, CandidateCheckpoint):
            result = CandidateCheckpoint(
                candidate_id=candidate_id,
                stage=name,
                blocked=False,
                decision="completed",
                reason=f"{name} completed (no checkpoint returned)",
                payload=result if isinstance(result, dict) else {},
            )
        checkpoint = result
        duration = (time.monotonic() - t0) * 1000

        if hasattr(checkpoint, "stage"):
            await _record_event(db, candidate_id, org_id, name, checkpoint)

            stages_result.append(
                StageResult(
                    stage=name,
                    status="blocked" if checkpoint.blocked else "passed",
                    reason=checkpoint.reason,
                    blocker_codes=list(checkpoint.blocker_codes),
                    duration_ms=round(duration, 1),
                    payload=checkpoint.payload,
                )
            )
        else:
            stages_result.append(
                StageResult(
                    stage=name,
                    status="passed",
                    reason=f"{name} completed",
                    blocker_codes=[],
                    duration_ms=round(duration, 1),
                )
            )

        logger.info(
            "Pipeline %s stage=%s status=%s reason=%s (%.0fms)",
            candidate_id,
            name,
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
            return {"blocked": False, "raw": None, "reason": "skipped"}

        if new_status and new_status != current_status:
            await _update_candidate_status(db, candidate_id, new_status)
            current_status = new_status

        t0 = time.monotonic()
        try:
            raw = await method(command)
        except Exception as exc:
            logger.exception("Pipeline stage %s failed", name)
            duration = (time.monotonic() - t0) * 1000
            stages_result.append(
                StageResult(
                    stage=name,
                    status="blocked",
                    reason=f"Exception: {exc}",
                    blocker_codes=[f"{name}_exception"],
                    duration_ms=round(duration, 1),
                )
            )
            return None

        duration = (time.monotonic() - t0) * 1000
        output = raw.output if hasattr(raw, "output") else {}
        stages_result.append(
            StageResult(
                stage=name,
                status="passed",
                reason=f"Discovery complete: {len(output.get('sources', []))} sources found",
                blocker_codes=[],
                duration_ms=round(duration, 1),
            )
        )
        return {"blocked": False, "raw": raw, "reason": "ok"}

    source_checkpoint: dict[str, Any] | None = None
    last_successful_checkpoint: CandidateCheckpoint | None = None

    def _blocked() -> bool:
        return last_checkpoint is not None and last_checkpoint.blocked

    def _update_last(ck: CandidateCheckpoint) -> None:
        nonlocal last_checkpoint, last_successful_checkpoint
        if ck.blocked:
            last_checkpoint = ck
        else:
            last_successful_checkpoint = ck

    # --- Stage 1: Identity Resolution ---
    ck = await _run_stage("identity_resolution", runtime.resolve_candidate_identity, "identity_resolution")
    _update_last(ck)

    # --- Stage 2: Source Discovery ---
    if not _blocked():
        source_checkpoint = await _run_stage_source_discovery(
            "source_discovery",
            runtime.discover_candidate_sources,
            "source_discovery",
        )
        if source_checkpoint is None:
            last_checkpoint = _make_blocked("source_discovery", "returned None")
        elif source_checkpoint.get("blocked", False):
            last_checkpoint = CandidateCheckpoint(
                candidate_id=candidate_id,
                stage="source_discovery",
                blocked=True,
                decision="blocked",
                reason=source_checkpoint.get("reason", "blocked"),
            )

    # --- Stage 2b: Persist + validate individual sources ---
    if (
        not _blocked()
        and source_checkpoint
        and not source_checkpoint.get("blocked", True)
        and source_checkpoint.get("raw") is not None
    ):
        await _run_stage(
            "source_persist",
            runtime.persist_candidate_sources_and_gaps,
            None,
            transform=source_checkpoint["raw"],
            allow_persist_duplicate=True,
        )
        from database.models.investment_candidates import CandidateSourceRecord

        async with db.session() as session:
            unverified = (
                (
                    await session.execute(
                        sa.select(CandidateSourceRecord).where(
                            CandidateSourceRecord.candidate_id == candidate_id,
                            CandidateSourceRecord.status == "discovered",
                        )
                    )
                )
                .scalars()
                .all()
            )
        if unverified:
            from ia_investing.orchestration.activities.candidate_intelligence import CandidateSourceValidationInput

            vc = 0
            for src in unverified:
                try:
                    await runtime.validate_supplied_candidate_source(
                        CandidateSourceValidationInput(
                            candidate_id=candidate_id, source_id=src.id, organization_id=org_id
                        ),
                    )
                    vc += 1
                except Exception as exc:
                    logger.warning("Source validation failed for %s: %s", src.id, exc)
            stages_result.append(
                StageResult(
                    stage="source_individual_validation",
                    status="passed",
                    reason=f"Validated {vc}/{len(unverified)} sources",
                    blocker_codes=[],
                    duration_ms=0,
                )
            )

    # --- Stage 3: Source Validation ---
    if not _blocked():
        ck = await _run_stage("source_validation", runtime.validate_candidate_sources, "source_validation")
        _update_last(ck)

    # --- Stage 3b: Auto-resolve gaps ---
    if not _blocked():
        from database.models.investment_candidates import CandidateGapRecord, CandidateSourceRecord

        async with db.session() as session:
            open_gaps = (
                (
                    await session.execute(
                        sa.select(CandidateGapRecord).where(
                            CandidateGapRecord.candidate_id == candidate_id,
                            CandidateGapRecord.status == "open",
                        )
                    )
                )
                .scalars()
                .all()
            )
            resolved_count = 0
            for gap in open_gaps:
                should_resolve = False
                if gap.source_kind:
                    has_v = (
                        await session.execute(
                            sa.select(sa.func.count(CandidateSourceRecord.id)).where(
                                CandidateSourceRecord.candidate_id == candidate_id,
                                CandidateSourceRecord.kind == gap.source_kind,
                                CandidateSourceRecord.status == "verified",
                            )
                        )
                    ).scalar()
                    if has_v and has_v > 0:
                        should_resolve = True
                if not should_resolve:
                    has_any = (
                        await session.execute(
                            sa.select(sa.func.count(CandidateSourceRecord.id)).where(
                                CandidateSourceRecord.candidate_id == candidate_id,
                                CandidateSourceRecord.status == "verified",
                            )
                        )
                    ).scalar()
                    if has_any and has_any >= 2:
                        should_resolve = True
                if should_resolve:
                    gap.status = "resolved"
                    gap.resolved_at = datetime.now(UTC)
                    gap.resolved_by = "sync_pipeline"
                    gap.resolution_notes = "Auto-resolved by pipeline"
                    resolved_count += 1
            if resolved_count > 0:
                await session.commit()
        if resolved_count > 0:
            stages_result.append(
                StageResult(
                    stage="gap_auto_resolution",
                    status="passed",
                    reason=f"Resolved {resolved_count} gap(s)",
                    blocker_codes=[],
                    duration_ms=0,
                )
            )

    # --- Stage 4: Readiness ---
    if not _blocked():
        ck = await _run_stage("readiness", runtime.evaluate_candidate_readiness, None)
        _update_last(ck)

    # --- Stage 5: Document Collection ---
    if not _blocked():
        async with db.session() as session:
            url_count = (
                await session.execute(
                    sa.select(sa.func.count(CandidateSourceRecord.id)).where(
                        CandidateSourceRecord.candidate_id == candidate_id,
                        CandidateSourceRecord.status == "verified",
                        CandidateSourceRecord.url.isnot(None),
                        CandidateSourceRecord.url != "",
                    )
                )
            ).scalar()
        if url_count and url_count > 0:
            ck = await _run_stage("document_collection", runtime.collect_candidate_documents, "document_collection")
            _update_last(ck)
        else:
            stages_result.append(
                StageResult(
                    stage="document_collection",
                    status="passed",
                    reason="Skipped: no verified sources with download URLs",
                    blocker_codes=[],
                    duration_ms=0,
                )
            )

    # --- Stage 6: Financial Ingestion ---
    if not _blocked():
        ck = await _run_stage(
            "financial_ingestion", runtime.ingest_candidate_financial_data, "data_quality", allow_persist_duplicate=True
        )
        if ck.blocked and ck.stage == "financial_ingestion":
            is_session_rollback = "transaction has been rolled back" in ck.reason
            is_no_data = "No DFP data found" in ck.reason or "financial_facts_missing" in ck.blocker_codes
            if is_session_rollback or is_no_data:
                async with db.session() as session:
                    fact_count = (
                        await session.execute(
                            sa.text(
                                "SELECT count(*) FROM financial_facts ff "
                                "JOIN reporting_periods rp ON rp.id = ff.reporting_period_id "
                                "JOIN issuers iss ON iss.id = ff.issuer_id "
                                "JOIN investment_candidates ic ON ic.issuer_id = iss.id "
                                "WHERE ic.id = :cid"
                            ),
                            {"cid": str(candidate_id)},
                        )
                    ).scalar()
                if fact_count and fact_count > 0:
                    stages_result[-1] = StageResult(
                        stage="financial_ingestion",
                        status="passed",
                        reason=f"Skipped: {fact_count} financial facts already ingested",
                        blocker_codes=[],
                        duration_ms=0,
                    )
                    ck = CandidateCheckpoint(
                        candidate_id=candidate_id,
                        stage="financial_ingestion",
                        blocked=False,
                        decision="continue",
                        reason=f"{fact_count} facts already ingested",
                    )
            if ck.blocked:
                last_checkpoint = ck

    # --- Stage 7: Data Quality ---
    if not _blocked():
        ck = await _run_stage("data_quality", runtime.validate_candidate_financial_data, "data_quality")
        _update_last(ck)

    # --- Stage 8: Fundamental Analysis ---
    if not _blocked():
        try:
            ck = await _run_stage(
                "fundamental_analysis", runtime.run_candidate_fundamental_analysis, "fundamental_analysis"
            )
            _update_last(ck)
        except Exception as exc:
            logger.warning("fundamental_analysis raised: %s", exc)
            stages_result.append(
                StageResult(
                    stage="fundamental_analysis",
                    status="blocked",
                    reason=f"Exception: {exc}",
                    blocker_codes=["fundamental_analysis_exception"],
                    duration_ms=0,
                )
            )
            last_checkpoint = CandidateCheckpoint(
                candidate_id=candidate_id,
                stage="fundamental_analysis",
                blocked=True,
                decision="blocked",
                reason=f"Exception: {exc}",
                blocker_codes=("fundamental_analysis_exception",),
            )

    # --- Stage 9: Risk Analysis ---
    if not _blocked():
        try:
            ck = await _run_stage("risk_analysis", runtime.run_candidate_risk_analysis, "risk_analysis")
            _update_last(ck)
        except Exception as exc:
            logger.warning("risk_analysis raised: %s", exc)
            stages_result.append(
                StageResult(
                    stage="risk_analysis",
                    status="blocked",
                    reason=f"Exception: {exc}",
                    blocker_codes=["risk_analysis_exception"],
                    duration_ms=0,
                )
            )
            last_checkpoint = CandidateCheckpoint(
                candidate_id=candidate_id,
                stage="risk_analysis",
                blocked=True,
                decision="blocked",
                reason=f"Exception: {exc}",
                blocker_codes=("risk_analysis_exception",),
            )

    # --- Stage 10: Committee Pack ---
    if not _blocked():
        try:
            ck = await _run_stage("committee_review", runtime.create_committee_pack, "committee_review")
            _update_last(ck)
        except Exception as exc:
            logger.warning("committee_review raised: %s", exc)
            stages_result.append(
                StageResult(
                    stage="committee_review",
                    status="blocked",
                    reason=f"Exception: {exc}",
                    blocker_codes=["committee_exception"],
                    duration_ms=0,
                )
            )
            last_checkpoint = CandidateCheckpoint(
                candidate_id=candidate_id,
                stage="committee_review",
                blocked=True,
                decision="blocked",
                reason=f"Exception: {exc}",
                blocker_codes=("committee_exception",),
            )

    # --- Finalize ---
    final_ckpt = last_checkpoint or last_successful_checkpoint
    if final_ckpt is None:
        final_ckpt = CandidateCheckpoint(
            candidate_id=candidate_id,
            stage="unknown",
            blocked=False,
            decision="completed",
            reason="All stages skipped",
        )

    try:
        workflow_result = await runtime.complete_candidate_analysis_run(
            command,
            final_ckpt,
        )
        final_status = workflow_result.status
    except Exception as exc:
        logger.warning("Failed to complete pipeline run for %s: %s", candidate_id, exc)
        final_status = (final_ckpt.blocked and "blocked") or "completed"

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
