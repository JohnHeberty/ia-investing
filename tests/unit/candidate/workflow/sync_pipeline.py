from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from ia_investing.orchestration.activities.candidate_intelligence import (
    CandidateCheckpoint,
    CandidateWorkflowResult,
)
from ia_investing.candidate_intelligence.sync_pipeline import (
    PipelineResult,
    StageResult,
    _make_blocked,
    run_candidate_pipeline,
)

pytestmark = pytest.mark.unit

CID = uuid4()
OID = uuid4()
RID = uuid4()


def _ok(stage: str = "test") -> CandidateCheckpoint:
    return CandidateCheckpoint(
        candidate_id=CID, stage=stage, blocked=False,
        decision="completed", reason=f"{stage} ok",
    )


def _blocked(stage: str = "test", reason: str = "blocked") -> CandidateCheckpoint:
    return CandidateCheckpoint(
        candidate_id=CID, stage=stage, blocked=True,
        decision="blocked", reason=reason,
        blocker_codes=(f"{stage}_blocked",),
    )


def _candidate(**kw: Any) -> MagicMock:
    c = MagicMock()
    c.id = CID
    c.organization_id = OID
    c.status = "identity_resolution"
    c.lock_version = 1
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def _run(**kw: Any) -> MagicMock:
    r = MagicMock()
    r.id = RID
    r.candidate_id = CID
    r.run_number = 1
    r.status = "queued"
    for k, v in kw.items():
        setattr(r, k, v)
    return r


def _make_result(candidate: Any = None, run: Any = None, scalar_val: Any = 0, list_val: Any = None) -> MagicMock:
    """Build a mock execute result that handles all access patterns."""
    r = MagicMock()
    r.scalars.return_value.one_or_none.return_value = candidate or run
    r.scalars.return_value.all.return_value = list_val if list_val is not None else []
    r.scalar.return_value = scalar_val
    return r


def _make_session(candidate: Any, run: Any = None, *, url_count: int = 0, unverified: Any = None, gaps: Any = None) -> MagicMock:
    """Build a universal session mock that handles all pipeline query patterns."""
    s = AsyncMock()

    main_result = _make_result(candidate=candidate, run=run)
    update_result = _make_result(candidate=candidate)
    event_result = _make_result(candidate=candidate)
    list_result = _make_result(list_val=unverified or [])
    gaps_result = _make_result(list_val=gaps or [])
    count_result = _make_result(scalar_val=url_count)

    call_count = {"n": 0}

    async def _execute(stmt, *args, **kwargs):
        call_count["n"] += 1
        # First 2 calls: candidate + run load
        if call_count["n"] == 1:
            return main_result
        if call_count["n"] == 2:
            return _make_result(run=run)
        # Subsequent calls: return a result that works for any access pattern
        # Update/status queries return candidate, list queries return []
        return update_result

    s.execute = AsyncMock(side_effect=_execute)
    s.add = MagicMock()
    s.commit = AsyncMock()
    s.rollback = AsyncMock()
    s.refresh = AsyncMock()
    return s


def _success_result() -> CandidateWorkflowResult:
    return CandidateWorkflowResult(
        candidate_id=CID, analysis_run_id=RID,
        status="completed", decision="pending",
        reason="done", blocker_codes=(),
    )


def _build_db(candidate: Any, run: Any = None, **session_kw: Any) -> MagicMock:
    """Build a DatabaseRuntime mock whose session() yields a universal session."""
    s = _make_session(candidate, run, **session_kw)
    db = MagicMock()

    @asynccontextmanager
    async def _ctx():
        yield s

    db.session = _ctx
    return db, s


def _patch_all(db_inst: MagicMock, runtime: Any = None, *, return_ctx: bool = False):
    """Context manager that patches all external deps for run_candidate_pipeline."""
    patches = [
        patch("ia_investing.candidate_intelligence.sync_pipeline.DatabaseRuntime"),
        patch("ia_investing.candidate_intelligence.sync_pipeline._get_database_url", return_value="pg://fake"),
        patch("ia_investing.platform.http.safe_client.SafeHttpClient"),
        patch("ia_investing.candidate_intelligence.sync_pipeline.ProductionCandidateRuntime"),
    ]
    if runtime is not None:
        patches[-1] = patch(
            "ia_investing.candidate_intelligence.sync_pipeline.ProductionCandidateRuntime",
            return_value=runtime,
        )
    from contextlib import ExitStack
    stack = ExitStack()
    mocks = [stack.enter_context(p) for p in patches]
    mocks[0].create.return_value = db_inst
    if return_ctx:
        return stack, mocks
    return stack


# -----------------------------------------------------------------------
# Unit: _make_blocked
# -----------------------------------------------------------------------

class TestMakeBlocked:
    def test_returns_blocked_checkpoint(self) -> None:
        ck = _make_blocked("identity_resolution", "no data")
        assert ck.blocked is True
        assert ck.stage == "identity_resolution"
        assert ck.reason == "no data"
        assert ck.blocker_codes == ("identity_resolution_blocked",)


# -----------------------------------------------------------------------
# Unit: StageResult / PipelineResult dataclasses
# -----------------------------------------------------------------------

class TestDataclasses:
    def test_stage_result_defaults(self) -> None:
        sr = StageResult(stage="x", status="passed", reason="ok", blocker_codes=[], duration_ms=1.0)
        assert sr.payload is None

    def test_pipeline_result_defaults(self) -> None:
        pr = PipelineResult(candidate_id=CID, run_id=RID, final_status="completed")
        assert pr.stages == []
        assert pr.total_duration_ms == 0.0


# -----------------------------------------------------------------------
# Integration: run_candidate_pipeline — candidate not found
# -----------------------------------------------------------------------

class TestPipelineNotFound:
    @pytest.mark.asyncio
    async def test_returns_failed_when_missing(self) -> None:
        s = AsyncMock()
        nr = MagicMock()
        nr.scalars.return_value.one_or_none.return_value = None
        s.execute = AsyncMock(return_value=nr)
        db_inst = MagicMock()

        @asynccontextmanager
        async def _ctx():
            yield s
        db_inst.session = _ctx

        with _patch_all(db_inst):
            result = await run_candidate_pipeline(CID, OID)

        assert result.final_status == "failed"
        assert result.stages == []


# -----------------------------------------------------------------------
# Integration: run_candidate_pipeline — identity resolution blocked
# -----------------------------------------------------------------------

class TestPipelineBlocked:
    @pytest.mark.asyncio
    async def test_blocked_at_identity_stops_pipeline(self) -> None:
        cand = _candidate()
        rn = _run()
        db_inst, session = _build_db(cand, rn)

        rt = MagicMock()
        rt.resolve_candidate_identity = AsyncMock(return_value=_blocked("identity_resolution", "no data"))
        rt.complete_candidate_analysis_run = AsyncMock(return_value=CandidateWorkflowResult(
            candidate_id=CID, analysis_run_id=RID,
            status="blocked", decision="pending",
            reason="blocked", blocker_codes=("identity_resolution_blocked",),
        ))

        with _patch_all(db_inst, rt):
            result = await run_candidate_pipeline(CID, OID)

        stages = [st.stage for st in result.stages]
        assert "identity_resolution" in stages
        assert "source_discovery" not in stages
        assert "data_quality" not in stages
        assert result.final_status == "blocked"


# -----------------------------------------------------------------------
# Integration: run_candidate_pipeline — exception in stage
# -----------------------------------------------------------------------

class TestPipelineException:
    @pytest.mark.asyncio
    async def test_exception_in_identity_blocked(self) -> None:
        cand = _candidate()
        rn = _run()
        db_inst, session = _build_db(cand, rn)

        rt = MagicMock()
        rt.resolve_candidate_identity = AsyncMock(side_effect=RuntimeError("boom"))
        rt.complete_candidate_analysis_run = AsyncMock(return_value=CandidateWorkflowResult(
            candidate_id=CID, analysis_run_id=RID,
            status="blocked", decision="pending",
            reason="exception", blocker_codes=("identity_resolution_exception",),
        ))

        with _patch_all(db_inst, rt):
            result = await run_candidate_pipeline(CID, OID)

        assert result.final_status == "blocked"
        id_stage = [st for st in result.stages if st.stage == "identity_resolution"]
        assert len(id_stage) == 1
        assert id_stage[0].status == "blocked"
        assert "boom" in id_stage[0].reason


# -----------------------------------------------------------------------
# Integration: run_candidate_pipeline — skip_stages
# -----------------------------------------------------------------------

class TestPipelineSkip:
    @pytest.mark.asyncio
    async def test_skip_source_validation_method_not_called(self) -> None:
        cand = _candidate()
        rn = _run()
        db_inst, session = _build_db(cand, rn)

        rt = MagicMock()
        rt.resolve_candidate_identity = AsyncMock(return_value=_ok("identity_resolution"))
        rt.discover_candidate_sources = AsyncMock(return_value=MagicMock(output={"sources": []}))
        rt.persist_candidate_sources_and_gaps = AsyncMock(return_value=_ok("source_persist"))
        rt.validate_candidate_sources = AsyncMock(return_value=_ok("source_validation"))
        rt.evaluate_candidate_readiness = AsyncMock(return_value=_ok("readiness"))
        rt.collect_candidate_documents = AsyncMock(return_value=_ok("document_collection"))
        rt.ingest_candidate_financial_data = AsyncMock(return_value=_ok("financial_ingestion"))
        rt.validate_candidate_financial_data = AsyncMock(return_value=_ok("data_quality"))
        rt.run_candidate_fundamental_analysis = AsyncMock(return_value=_ok("fundamental_analysis"))
        rt.run_candidate_risk_analysis = AsyncMock(return_value=_ok("risk_analysis"))
        rt.create_committee_pack = AsyncMock(return_value=_ok("committee_review"))
        rt.complete_candidate_analysis_run = AsyncMock(return_value=_success_result())

        with _patch_all(db_inst, rt):
            result = await run_candidate_pipeline(
                CID, OID, skip_stages=["source_validation"],
            )

        # Skipped stages are not appended to stages_result (early return before append)
        # Verify the skipped stage's runtime method was never called
        rt.validate_candidate_sources.assert_not_called()
        # Pipeline should still complete successfully
        assert result.final_status == "completed"
        stage_names = [st.stage for st in result.stages]
        assert "source_validation" not in stage_names
        assert "readiness" in stage_names  # stages after skip still run


# -----------------------------------------------------------------------
# Integration: run_candidate_pipeline — complete_candidate_analysis_run fails
# -----------------------------------------------------------------------

class TestPipelineFinalizeError:
    @pytest.mark.asyncio
    async def test_finalize_exception_uses_checkpoint_status(self) -> None:
        cand = _candidate()
        rn = _run()
        db_inst, session = _build_db(cand, rn)

        rt = MagicMock()
        rt.resolve_candidate_identity = AsyncMock(return_value=_ok("identity_resolution"))
        rt.discover_candidate_sources = AsyncMock(return_value=MagicMock(output={"sources": []}))
        rt.persist_candidate_sources_and_gaps = AsyncMock(return_value=_ok("source_persist"))
        rt.validate_candidate_sources = AsyncMock(return_value=_ok("source_validation"))
        rt.evaluate_candidate_readiness = AsyncMock(return_value=_ok("readiness"))
        rt.collect_candidate_documents = AsyncMock(return_value=_ok("document_collection"))
        rt.ingest_candidate_financial_data = AsyncMock(return_value=_ok("financial_ingestion"))
        rt.validate_candidate_financial_data = AsyncMock(return_value=_ok("data_quality"))
        rt.run_candidate_fundamental_analysis = AsyncMock(return_value=_ok("fundamental_analysis"))
        rt.run_candidate_risk_analysis = AsyncMock(return_value=_blocked("risk_analysis", "risk failure"))
        rt.create_committee_pack = AsyncMock(return_value=_ok("committee_review"))
        rt.complete_candidate_analysis_run = AsyncMock(side_effect=RuntimeError("finalize error"))

        with _patch_all(db_inst, rt):
            result = await run_candidate_pipeline(CID, OID)

        assert result.final_status == "blocked"
        risk_stages = [st for st in result.stages if st.stage == "risk_analysis"]
        assert len(risk_stages) == 1
        assert risk_stages[0].status == "blocked"


# -----------------------------------------------------------------------
# Integration: run_candidate_pipeline — no run record creates one
# -----------------------------------------------------------------------

class TestPipelineNewRun:
    @pytest.mark.asyncio
    async def test_creates_new_run_when_none_exists(self) -> None:
        cand = _candidate()
        db_inst, session = _build_db(cand, run=None)

        rt = MagicMock()
        rt.resolve_candidate_identity = AsyncMock(return_value=_blocked("identity_resolution", "blocked"))
        rt.complete_candidate_analysis_run = AsyncMock(return_value=CandidateWorkflowResult(
            candidate_id=CID, analysis_run_id=RID,
            status="blocked", decision="pending",
            reason="blocked", blocker_codes=("identity_resolution_blocked",),
        ))

        with _patch_all(db_inst, rt):
            result = await run_candidate_pipeline(CID, OID)

        assert result.final_status == "blocked"
        assert session.add.called
