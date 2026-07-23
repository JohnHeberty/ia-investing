from __future__ import annotations

import hashlib
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from conftest import _postgres_reachable  # type: ignore[import-not-found]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from database.models.catalog import Issuer
from database.models.identity import Organization
from database.models.instrument_master import Instrument, Listing
from database.models.investment_candidates import (
    CandidateAnalysisRunRecord,
    CandidateEventRecord,
    CandidateGapRecord,
    CandidateSourceRecord,
    ExplorationRunRecord,
    InvestmentCandidateRecord,
)
from ia_investing.integrations.production_runtime import (
    ProductionCandidateRuntime,
    _stage_blocked,
)
from ia_investing.orchestration.activities.candidate_intelligence import (
    CandidateCheckpoint,
    CandidateWorkflowInput,
    ExplorationFindings,
    ExplorationShortlist,
    ExplorationWorkflowInput,
    SourceDiscoveryCheckpoint,
    candidate_activity_runtime_configured,
    reset_candidate_activity_runtime_for_tests,
)
from ia_investing.platform.database.runtime import DatabaseRuntime

_SKIP_DB = pytest.mark.skipif(
    not _postgres_reachable(),
    reason="PostgreSQL not reachable — start with: docker compose --profile test up -d",
)

pytestmark = pytest.mark.integration

_DATA_AS_OF = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_org(session: AsyncSession) -> Organization:
    org = Organization(
        id=uuid4(),
        slug=f"test-candidate-{uuid4().hex[:8]}",
        display_name="Test Candidate Org",
    )
    session.add(org)
    return org


def _make_candidate(session: AsyncSession, org_id: UUID) -> InvestmentCandidateRecord:
    hash_ = hashlib.sha256(uuid4().bytes).hexdigest()
    c = InvestmentCandidateRecord(
        id=uuid4(),
        organization_id=org_id,
        origin="manual",
        status="identity_resolution",
        ticker="TEST4",
        created_by="test",
        idempotency_key=f"test-key-{uuid4().hex[:8]}",
        request_hash=hash_,
    )
    session.add(c)
    return c


def _make_analysis_run(session: AsyncSession, candidate_id: UUID) -> CandidateAnalysisRunRecord:
    r = CandidateAnalysisRunRecord(
        id=uuid4(),
        candidate_id=candidate_id,
        run_number=1,
        trigger="user_completion",
        status="running",
        requested_by="test",
        requested_at=_DATA_AS_OF,
        data_as_of=_DATA_AS_OF,
    )
    session.add(r)
    return r


def _make_issuer_instrument_listing(session: AsyncSession) -> tuple[Issuer, Instrument, Listing]:
    issuer = Issuer(id=uuid4(), name_pt="Test Issuer S.A.")
    session.add(issuer)
    instrument = Instrument(id=uuid4(), issuer_id=issuer.id, instrument_type="common_share")
    session.add(instrument)
    listing = Listing(
        id=uuid4(),
        instrument_id=instrument.id,
        exchange_code="B3",
        ticker="TEST4",
        valid_from=date(2020, 1, 1),
    )
    session.add(listing)
    return issuer, instrument, listing


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_runtime(engine: AsyncEngine) -> DatabaseRuntime:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    return DatabaseRuntime(engine=engine, sessions=maker)


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_global_runtime() -> AsyncGenerator[None]:
    yield
    reset_candidate_activity_runtime_for_tests()


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


_BOOTSTRAP_FACTORY = "tests.unit.dummy_candidate_runtime:create_mock_runtime"


def _patch_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    enabled: bool,
    factory: str = "",
) -> None:
    from ia_investing.settings import CandidateSettings, Settings, get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(
        "ia_investing.candidate_intelligence.bootstrap.get_settings",
        lambda: Settings(candidate=CandidateSettings(enabled=enabled, runtime_factory=factory)),
    )


async def test_bootstrap_configures_global_runtime(
    monkeypatch: pytest.MonkeyPatch, db_runtime: DatabaseRuntime
) -> None:
    _patch_settings(monkeypatch, enabled=True, factory=_BOOTSTRAP_FACTORY)

    from ia_investing.candidate_intelligence.bootstrap import (
        configure_candidate_runtime_from_environment,
    )

    result = await configure_candidate_runtime_from_environment(db=db_runtime)
    assert result is True
    assert candidate_activity_runtime_configured() is True


async def test_bootstrap_skips_when_disabled(db_runtime: DatabaseRuntime) -> None:
    from ia_investing.candidate_intelligence.bootstrap import (
        configure_candidate_runtime_from_environment,
    )

    result = await configure_candidate_runtime_from_environment(db=db_runtime)
    assert result is False
    assert candidate_activity_runtime_configured() is False


async def test_bootstrap_fails_on_incompatible_factory(
    monkeypatch: pytest.MonkeyPatch, db_runtime: DatabaseRuntime
) -> None:
    _patch_settings(monkeypatch, enabled=True, factory="builtins:str")

    from ia_investing.candidate_intelligence.bootstrap import (
        configure_candidate_runtime_from_environment,
    )

    with pytest.raises(RuntimeError, match="incompatible"):
        await configure_candidate_runtime_from_environment(db=db_runtime)

    assert candidate_activity_runtime_configured() is False


# ---------------------------------------------------------------------------
# Persist sources & gaps
# ---------------------------------------------------------------------------


@_SKIP_DB
async def test_persist_sources_and_gaps_writes_records(db_runtime: DatabaseRuntime) -> None:
    async with db_runtime.session() as session:
        org = _make_org(session)
        candidate = _make_candidate(session, org.id)
        await session.commit()

    command = CandidateWorkflowInput(
        candidate_id=candidate.id,
        analysis_run_id=uuid4(),
        organization_id=org.id,
        data_as_of=_DATA_AS_OF,
        allow_incomplete=False,
        correlation_id=uuid4(),
    )
    checkpoint = SourceDiscoveryCheckpoint(
        command=command,
        output={
            "stage": "source_discovery",
            "sources": [
                {
                    "kind": "issuer_record",
                    "url": "",
                    "status": "verified",
                    "verification_method": "database",
                    "confidence": 1.0,
                    "official": True,
                    "discovered_by": "system",
                    "evidence": {"issuer_name": "Test Issuer"},
                },
                {
                    "kind": "listing:B3",
                    "url": "",
                    "status": "verified",
                    "verification_method": "database",
                    "confidence": 1.0,
                    "official": True,
                    "discovered_by": "system",
                    "evidence": {"exchange": "B3"},
                },
            ],
            "gaps": [
                {
                    "code": "investor_relations_missing",
                    "title": "Investor relations page not found",
                    "level": "blocking",
                    "requested_user_action": "Provide the IR URL manually.",
                    "source_kind": "investor_relations",
                },
            ],
            "summary": "Found 2 sources, 1 gap.",
        },
    )

    runtime = ProductionCandidateRuntime(db=db_runtime)
    await runtime.persist_candidate_sources_and_gaps(checkpoint)

    async with db_runtime.session() as session:
        sources = (
            (
                await session.execute(
                    select(CandidateSourceRecord).where(
                        CandidateSourceRecord.candidate_id == candidate.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        gaps = (
            (
                await session.execute(
                    select(CandidateGapRecord).where(
                        CandidateGapRecord.candidate_id == candidate.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        events = (
            (
                await session.execute(
                    select(CandidateEventRecord).where(
                        CandidateEventRecord.candidate_id == candidate.id,
                    )
                )
            )
            .scalars()
            .all()
        )

    assert len(sources) == 2
    assert {s.kind for s in sources} == {"issuer_record", "listing:B3"}
    assert all(s.status == "verified" for s in sources)

    assert len(gaps) == 1
    assert gaps[0].code == "investor_relations_missing"
    assert gaps[0].status == "open"
    assert gaps[0].level == "blocking"

    assert len(events) == 1
    assert events[0].event_type == "sources_persisted"
    assert events[0].payload.get("source_count") == 2
    assert events[0].payload.get("gap_count") == 1


@_SKIP_DB
async def test_persist_sources_deduplicates_on_repeat(db_runtime: DatabaseRuntime) -> None:
    async with db_runtime.session() as session:
        org = _make_org(session)
        candidate = _make_candidate(session, org.id)
        await session.commit()

    command = CandidateWorkflowInput(
        candidate_id=candidate.id,
        analysis_run_id=uuid4(),
        organization_id=org.id,
        data_as_of=_DATA_AS_OF,
        allow_incomplete=False,
        correlation_id=uuid4(),
    )
    checkpoint = SourceDiscoveryCheckpoint(
        command=command,
        output={
            "stage": "source_discovery",
            "sources": [
                {
                    "kind": "issuer_record",
                    "url": "",
                    "status": "verified",
                    "verification_method": "database",
                    "confidence": 1.0,
                    "official": True,
                    "discovered_by": "system",
                    "evidence": {},
                },
            ],
            "gaps": [],
            "summary": "1 source.",
        },
    )

    runtime = ProductionCandidateRuntime(db=db_runtime)
    await runtime.persist_candidate_sources_and_gaps(checkpoint)
    await runtime.persist_candidate_sources_and_gaps(checkpoint)

    async with db_runtime.session() as session:
        sources = (
            (
                await session.execute(
                    select(CandidateSourceRecord).where(
                        CandidateSourceRecord.candidate_id == candidate.id,
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(sources) == 1


# ---------------------------------------------------------------------------
# Complete analysis run
# ---------------------------------------------------------------------------


@_SKIP_DB
async def test_complete_run_updates_status(db_runtime: DatabaseRuntime) -> None:
    async with db_runtime.session() as session:
        org = _make_org(session)
        candidate = _make_candidate(session, org.id)
        run = _make_analysis_run(session, candidate.id)
        await session.commit()

    runtime = ProductionCandidateRuntime(db=db_runtime)
    command = CandidateWorkflowInput(
        candidate_id=candidate.id,
        analysis_run_id=run.id,
        organization_id=org.id,
        data_as_of=_DATA_AS_OF,
        allow_incomplete=False,
        correlation_id=uuid4(),
    )
    checkpoint = CandidateCheckpoint(
        candidate_id=candidate.id,
        stage="fundamental_analysis",
        blocked=False,
        decision="continue",
        reason="All checks passed.",
    )

    result = await runtime.complete_candidate_analysis_run(command, checkpoint)

    assert result.status == "succeeded"
    assert result.decision == "continue"

    async with db_runtime.session() as session:
        updated = await session.get(CandidateAnalysisRunRecord, run.id)
    assert updated is not None
    assert updated.status == "succeeded"
    assert updated.completed_at is not None


@_SKIP_DB
async def test_complete_run_records_blocked_status(db_runtime: DatabaseRuntime) -> None:
    async with db_runtime.session() as session:
        org = _make_org(session)
        candidate = _make_candidate(session, org.id)
        run = _make_analysis_run(session, candidate.id)
        await session.commit()

    runtime = ProductionCandidateRuntime(db=db_runtime)
    command = CandidateWorkflowInput(
        candidate_id=candidate.id,
        analysis_run_id=run.id,
        organization_id=org.id,
        data_as_of=_DATA_AS_OF,
        allow_incomplete=False,
        correlation_id=uuid4(),
    )
    checkpoint = _stage_blocked(
        command,
        stage="fundamental_analysis",
        reason="No agent provider available.",
        blocker_codes=("provider_unavailable",),
    )

    result = await runtime.complete_candidate_analysis_run(command, checkpoint)

    assert result.status == "blocked"
    assert "provider_unavailable" in result.blocker_codes

    async with db_runtime.session() as session:
        updated = await session.get(CandidateAnalysisRunRecord, run.id)
    assert updated is not None
    assert updated.status == "blocked"
    assert updated.blocker_codes == ["provider_unavailable"]


# ---------------------------------------------------------------------------
# Screen equity universe
# ---------------------------------------------------------------------------


@_SKIP_DB
async def test_screen_equity_universe_returns_instruments(db_runtime: DatabaseRuntime) -> None:
    async with db_runtime.session() as session:
        _make_issuer_instrument_listing(session)
        await session.commit()

    runtime = ProductionCandidateRuntime(db=db_runtime)
    command = ExplorationWorkflowInput(
        exploration_run_id=uuid4(),
        organization_id=uuid4(),
        data_as_of=_DATA_AS_OF,
        correlation_id=uuid4(),
    )

    result = await runtime.screen_equity_universe(command)

    assert result.universe_size >= 1
    matches = [s for s in result.securities if s.get("symbol") == "TEST4"]
    assert len(matches) == 1
    assert matches[0]["issuer_name"] == "Test Issuer S.A."


# ---------------------------------------------------------------------------
# Evaluate readiness
# ---------------------------------------------------------------------------


@_SKIP_DB
async def test_evaluate_readiness_detects_blockers(db_runtime: DatabaseRuntime) -> None:
    async with db_runtime.session() as session:
        org = _make_org(session)
        candidate = _make_candidate(session, org.id)
        candidate.status = "source_discovery"
        candidate.instrument_id = uuid4()
        candidate.issuer_id = uuid4()
        gap = CandidateGapRecord(
            id=uuid4(),
            candidate_id=candidate.id,
            code="investor_relations_missing",
            title="IR page not found",
            level="blocking",
            status="open",
            requested_user_action="Provide IR URL",
        )
        session.add(gap)
        await session.commit()

    runtime = ProductionCandidateRuntime(db=db_runtime)
    command = CandidateWorkflowInput(
        candidate_id=candidate.id,
        analysis_run_id=uuid4(),
        organization_id=org.id,
        data_as_of=_DATA_AS_OF,
        allow_incomplete=False,
        correlation_id=uuid4(),
    )

    result = await runtime.evaluate_candidate_readiness(command)

    assert result.blocked is True
    assert "investor_relations_missing" in result.blocker_codes


@_SKIP_DB
async def test_evaluate_readiness_passes_when_no_blockers(db_runtime: DatabaseRuntime) -> None:
    async with db_runtime.session() as session:
        org = _make_org(session)
        candidate = _make_candidate(session, org.id)
        candidate.status = "source_discovery"
        candidate.instrument_id = uuid4()
        candidate.issuer_id = uuid4()
        gap = CandidateGapRecord(
            id=uuid4(),
            candidate_id=candidate.id,
            code="investor_relations_missing",
            title="IR page not found",
            level="blocking",
            status="resolved",
            requested_user_action="Provide IR URL",
            resolved_at=_DATA_AS_OF,
            resolved_by="test",
            resolution_notes="Provided manually",
        )
        session.add(gap)
        await session.commit()

    runtime = ProductionCandidateRuntime(db=db_runtime)
    command = CandidateWorkflowInput(
        candidate_id=candidate.id,
        analysis_run_id=uuid4(),
        organization_id=org.id,
        data_as_of=_DATA_AS_OF,
        allow_incomplete=False,
        correlation_id=uuid4(),
    )

    result = await runtime.evaluate_candidate_readiness(command)
    assert result.blocked is False


# ---------------------------------------------------------------------------
# Persist exploration suggestions
# ---------------------------------------------------------------------------


@_SKIP_DB
async def test_persist_exploration_suggestions_updates_run(db_runtime: DatabaseRuntime) -> None:
    async with db_runtime.session() as session:
        org = _make_org(session)
        run = ExplorationRunRecord(
            id=uuid4(),
            organization_id=org.id,
            status="running",
            strategy_codes=["momentum"],
            requested_by="test",
            data_as_of=_DATA_AS_OF,
            minimum_liquidity=1_000_000,
            maximum_suggestions=10,
        )
        session.add(run)
        await session.commit()

    runtime = ProductionCandidateRuntime(db=db_runtime)
    command = ExplorationWorkflowInput(
        exploration_run_id=run.id,
        organization_id=org.id,
        data_as_of=_DATA_AS_OF,
        correlation_id=uuid4(),
    )

    shortlist = ExplorationShortlist(
        command=command,
        securities=(),
        universe_size=50,
        eligible_size=30,
    )
    findings = ExplorationFindings(
        shortlist=shortlist,
        suggestions=(),
        limitations=(),
    )

    result = await runtime.persist_exploration_suggestions(findings)

    assert result.status == "succeeded"
    assert result.universe_size == 50
    assert result.eligible_size == 30

    async with db_runtime.session() as session:
        updated = await session.get(ExplorationRunRecord, run.id)
    assert updated is not None
    assert updated.status == "succeeded"
    assert updated.completed_at is not None
    assert updated.universe_size == 50
    assert updated.eligible_size == 30
