from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from unittest.mock import AsyncMock
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
    ExplorationSuggestionRecord,
    InvestmentCandidateRecord,
)
from ia_investing.integrations.production_runtime import ProductionCandidateRuntime
from ia_investing.orchestration.activities.candidate_intelligence import (
    CandidateCheckpoint,
    CandidateSourceValidationInput,
    CandidateWorkflowInput,
    ExplorationFindings,
    ExplorationWorkflowInput,
    ExplorationWorkflowResult,
    SourceDiscoveryCheckpoint,
)
from ia_investing.platform.database.runtime import DatabaseRuntime
from ia_investing.platform.http.safe_client import SafeHttpClient, ValidatedHttpResponse

_SKIP_DB = pytest.mark.skipif(
    not _postgres_reachable(),
    reason="PostgreSQL not reachable",
)

pytestmark = pytest.mark.integration

_DATA_AS_OF = datetime.now(UTC)


def _make_org(session: AsyncSession) -> Organization:
    org = Organization(
        id=uuid4(),
        slug=f"scenario-{uuid4().hex[:8]}",
        display_name="Scenario Org",
    )
    session.add(org)
    return org


def _make_candidate(
    session: AsyncSession, org_id: UUID, **kw: object
) -> InvestmentCandidateRecord:
    h = hashlib.sha256(uuid4().bytes).hexdigest()
    c = InvestmentCandidateRecord(
        id=uuid4(),
        organization_id=org_id,
        origin="manual",
        status="identity_resolution",
        ticker="SCEN4",
        created_by="test",
        idempotency_key=f"scenario-{uuid4().hex[:8]}",
        request_hash=h,
        **kw,
    )
    session.add(c)
    return c


def _make_analysis_run(
    session: AsyncSession, candidate_id: UUID
) -> CandidateAnalysisRunRecord:
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


def _make_issuer_instrument_listing(
    session: AsyncSession, *, ticker: str = "SCEN4"
) -> tuple[Issuer, Instrument, Listing]:
    issuer = Issuer(
        id=uuid4(), name_pt="Scenario Issuer S.A.", cnpj="99888777000199"
    )
    session.add(issuer)
    instrument = Instrument(
        id=uuid4(), issuer_id=issuer.id, instrument_type="common_share"
    )
    session.add(instrument)
    listing = Listing(
        id=uuid4(),
        instrument_id=instrument.id,
        exchange_code="B3",
        ticker=ticker,
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


# ---------------------------------------------------------------------------
# Scenario A — Full Flow (Happy Path)
# ---------------------------------------------------------------------------


@_SKIP_DB
async def test_scenario_a_full_flow(db_runtime: DatabaseRuntime) -> None:
    async with db_runtime.session() as session:
        org = _make_org(session)
        issuer, instrument, _listing = _make_issuer_instrument_listing(session)
        candidate = _make_candidate(session, org.id)
        run = _make_analysis_run(session, candidate.id)
        await session.commit()

    candidate_id = candidate.id
    org_id = org.id
    command = CandidateWorkflowInput(
        candidate_id=candidate_id,
        analysis_run_id=run.id,
        organization_id=org_id,
        data_as_of=_DATA_AS_OF,
        allow_incomplete=False,
        correlation_id=uuid4(),
    )
    runtime = ProductionCandidateRuntime(db=db_runtime)

    # 1. Identity resolution — finds issuer+instrument via ticker lookup
    identity = await runtime.resolve_candidate_identity(command)
    assert identity.blocked is False, f"Identity blocked: {identity.reason}"
    assert identity.decision == "continue"

    async with db_runtime.session() as session:
        updated = await session.get(InvestmentCandidateRecord, candidate_id)
    assert updated is not None
    assert updated.issuer_id == issuer.id
    assert updated.instrument_id == instrument.id

    # 2. Source discovery
    discovery = await runtime.discover_candidate_sources(command)
    assert len(discovery.output["sources"]) >= 1

    # 3. Persist sources and gaps
    await runtime.persist_candidate_sources_and_gaps(discovery)

    async with db_runtime.session() as session:
        sources = (
            (
                await session.execute(
                    select(CandidateSourceRecord).where(
                        CandidateSourceRecord.candidate_id == candidate_id
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
                        CandidateGapRecord.candidate_id == candidate_id
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
                        CandidateEventRecord.candidate_id == candidate_id
                    )
                )
            )
            .scalars()
            .all()
        )

    assert len(sources) >= 1
    assert len(events) >= 1
    assert events[-1].event_type == "sources_persisted"

    # 4. Resolve any blocking gaps before readiness
    for gap in gaps:
        if gap.level == "blocking" and gap.status == "open":
            async with db_runtime.session() as session:
                g = await session.get(CandidateGapRecord, gap.id)
                if g is not None:
                    g.status = "resolved"
                    g.resolved_at = _DATA_AS_OF
                    g.resolved_by = "test"
                    g.resolution_notes = "Resolved for scenario A"
                await session.commit()

    # 5. Readiness
    readiness = await runtime.evaluate_candidate_readiness(command)
    assert readiness.blocked is False, f"Readiness blocked: {readiness.reason}"

    # 6. Complete the analysis run
    checkpoint = CandidateCheckpoint(
        candidate_id=candidate_id,
        stage="committee_review",
        blocked=False,
        decision="approve",
        reason="All checks passed in scenario A.",
        payload={"scenario": "A"},
    )
    result = await runtime.complete_candidate_analysis_run(command, checkpoint)
    assert result.status == "succeeded"
    assert result.decision == "approve"

    async with db_runtime.session() as session:
        run_db = await session.get(CandidateAnalysisRunRecord, run.id)
    assert run_db is not None
    assert run_db.status == "succeeded"
    assert run_db.completed_at is not None


# ---------------------------------------------------------------------------
# Scenario B — RI not found → User URL → Validated → Gap resolved
# ---------------------------------------------------------------------------


@_SKIP_DB
async def test_scenario_b_ri_missing_resolved(db_runtime: DatabaseRuntime) -> None:
    async with db_runtime.session() as session:
        org = _make_org(session)
        _issuer, instrument, _listing = _make_issuer_instrument_listing(session)
        candidate = _make_candidate(session, org.id)
        candidate.issuer_id = _issuer.id
        candidate.instrument_id = instrument.id
        candidate.status = "source_discovery"
        run = _make_analysis_run(session, candidate.id)
        await session.commit()

    command = CandidateWorkflowInput(
        candidate_id=candidate.id,
        analysis_run_id=run.id,
        organization_id=org.id,
        data_as_of=_DATA_AS_OF,
        allow_incomplete=False,
        correlation_id=uuid4(),
    )
    runtime = ProductionCandidateRuntime(db=db_runtime)

    # 1. Discover sources — expect investor_relations_missing gap
    discovery = await runtime.discover_candidate_sources(command)
    gap_codes = [g["code"] for g in discovery.output["gaps"]]
    assert "investor_relations_missing" in gap_codes

    # 2. Persist the gap
    await runtime.persist_candidate_sources_and_gaps(discovery)

    async with db_runtime.session() as session:
        gaps = (
            (
                await session.execute(
                    select(CandidateGapRecord).where(
                        CandidateGapRecord.candidate_id == candidate.id
                    )
                )
            )
            .scalars()
            .all()
        )
    ir_gaps = [g for g in gaps if g.code == "investor_relations_missing"]
    assert len(ir_gaps) == 1
    assert ir_gaps[0].status == "open"

    # 3. Readiness should be blocked
    readiness = await runtime.evaluate_candidate_readiness(command)
    assert readiness.blocked is True
    assert "investor_relations_missing" in readiness.blocker_codes

    # 4. User supplies a URL → create source record
    async with db_runtime.session() as session:
        source = CandidateSourceRecord(
            id=uuid4(),
            candidate_id=candidate.id,
            kind="investor_relations",
            url="https://ri.scenarioissuer.com.br",
            normalized_url_hash=hashlib.sha256(
                b"https://ri.scenarioissuer.com.br"
            ).hexdigest(),
            status="discovered",
            verification_method="user_supplied",
            confidence=Decimal("0.5"),
            official=False,
            discovered_by="user",
        )
        session.add(source)
        await session.commit()
        source_id = source.id

    # 5. Validate the URL — mock HTTP response with identity signals
    expected_content = (
        b"<html><title>Scenario Issuer S.A. RI</title>"
        b"<p>CNPJ: 99.888.777/0001-99</p>"
        b"<p>SCEN4 na B3</p></html>"
    )
    runtime._http = cast(
        SafeHttpClient,
        _mock_http_client(
            status_code=200, content=expected_content, final_url="https://ri.scenarioissuer.com.br"
        ),
    )

    validation_input = CandidateSourceValidationInput(
        candidate_id=candidate.id,
        source_id=source_id,
        organization_id=org.id,
        correlation_id=uuid4(),
    )
    validation = await runtime.validate_supplied_candidate_source(validation_input)
    assert validation.status == "verified", (
        f"Expected verified, got {validation.status}: {validation.reason}"
    )
    assert validation.official is True

    # 6. Gap should now be resolved
    async with db_runtime.session() as session:
        source_db = await session.get(CandidateSourceRecord, source_id)
        gaps = (
            (
                await session.execute(
                    select(CandidateGapRecord).where(
                        CandidateGapRecord.candidate_id == candidate.id
                    )
                )
            )
            .scalars()
            .all()
        )
    assert source_db is not None
    assert source_db.status == "verified"
    assert source_db.official is True

    ir_gaps = [g for g in gaps if g.code == "investor_relations_missing"]
    assert len(ir_gaps) == 1
    assert ir_gaps[0].status == "resolved"

    # 7. Readiness should now pass
    readiness = await runtime.evaluate_candidate_readiness(command)
    assert readiness.blocked is False, (
        f"Still blocked after resolving IR gap: {readiness.blocker_codes}"
    )


# ---------------------------------------------------------------------------
# Scenario C — Wrong URL (identity mismatch → rejected)
# ---------------------------------------------------------------------------


@_SKIP_DB
async def test_scenario_c_wrong_url_rejected(db_runtime: DatabaseRuntime) -> None:
    async with db_runtime.session() as session:
        org = _make_org(session)
        _issuer, _instrument, _listing = _make_issuer_instrument_listing(session)
        candidate = _make_candidate(session, org.id)
        candidate.issuer_id = _issuer.id
        candidate.instrument_id = _instrument.id
        candidate.legal_name = "Scenario Issuer S.A."
        _run = _make_analysis_run(session, candidate.id)
        await session.commit()

    async with db_runtime.session() as session:
        source = CandidateSourceRecord(
            id=uuid4(),
            candidate_id=candidate.id,
            kind="investor_relations",
            url="https://ri.differentcompany.com.br",
            normalized_url_hash=hashlib.sha256(
                b"https://ri.differentcompany.com.br"
            ).hexdigest(),
            status="discovered",
            verification_method="user_supplied",
            confidence=Decimal("0.5"),
            official=False,
            discovered_by="user",
        )
        session.add(source)
        await session.commit()
        source_id = source.id

    runtime = ProductionCandidateRuntime(db=db_runtime)
    runtime._http = cast(
        SafeHttpClient,
        _mock_http_client(
            status_code=200,
            content=b"<html><title>Different Company</title><p>Outra empresa</p></html>",
            final_url="https://ri.differentcompany.com.br",
        ),
    )

    validation_input = CandidateSourceValidationInput(
        candidate_id=candidate.id,
        source_id=source_id,
        organization_id=org.id,
        correlation_id=uuid4(),
    )
    validation = await runtime.validate_supplied_candidate_source(validation_input)
    assert validation.status == "rejected", f"Expected rejected, got {validation.status}"
    assert validation.official is False

    async with db_runtime.session() as session:
        source_db = await session.get(CandidateSourceRecord, source_id)
    assert source_db is not None
    assert source_db.status == "rejected"


# ---------------------------------------------------------------------------
# Scenario D — Explorer: universe → suggestions → persist
# ---------------------------------------------------------------------------


@_SKIP_DB
async def test_scenario_d_explorer_persists_suggestions(
    db_runtime: DatabaseRuntime,
) -> None:
    async with db_runtime.session() as session:
        org = _make_org(session)
        _iss, instrument, _listing = _make_issuer_instrument_listing(
            session, ticker="EXPL4"
        )
        await session.commit()

    runtime = ProductionCandidateRuntime(db=db_runtime)
    exploration_id = uuid4()
    org_id = org.id

    async with db_runtime.session() as session:
        run = ExplorationRunRecord(
            id=exploration_id,
            organization_id=org_id,
            status="running",
            strategy_codes=["momentum"],
            requested_by="test",
            data_as_of=_DATA_AS_OF,
            minimum_liquidity=1_000_000,
            maximum_suggestions=10,
        )
        session.add(run)
        await session.commit()

    command = ExplorationWorkflowInput(
        exploration_run_id=exploration_id,
        organization_id=org_id,
        data_as_of=_DATA_AS_OF,
        correlation_id=uuid4(),
    )

    # 1. Screen universe
    shortlist = await runtime.screen_equity_universe(command)
    assert shortlist.universe_size >= 1

    # 2. Explorer agent produces one suggestion
    suggestion: tuple[dict[str, object], ...] = (
        {
            "instrument_id": str(instrument.id),
            "symbol": "EXPL4",
            "issuer_name": "Scenario Issuer S.A.",
            "rationale": "Momentum candidate",
            "score": 0.85,
        },
    )
    findings = ExplorationFindings(
        shortlist=shortlist, suggestions=suggestion, limitations=()
    )

    # 3. Persist suggestions
    result: ExplorationWorkflowResult = (
        await runtime.persist_exploration_suggestions(findings)
    )
    assert result.status == "succeeded"
    assert result.suggestion_count >= 1
    assert result.universe_size == shortlist.universe_size

    async with db_runtime.session() as session:
        run_db = await session.get(ExplorationRunRecord, exploration_id)
        suggestions_db = (
            (
                await session.execute(
                    select(ExplorationSuggestionRecord).where(
                        ExplorationSuggestionRecord.exploration_run_id == exploration_id
                    )
                )
            )
            .scalars()
            .all()
        )
    assert run_db is not None
    assert run_db.status == "succeeded"
    assert len(suggestions_db) == 1
    assert suggestions_db[0].status == "new"
    assert suggestions_db[0].ticker == "EXPL4"
    assert suggestions_db[0].quantitative_score == Decimal("0.8500")


# ---------------------------------------------------------------------------
# Scenario F — Idempotency
# ---------------------------------------------------------------------------


@_SKIP_DB
async def test_scenario_f_idempotency(db_runtime: DatabaseRuntime) -> None:
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
    source_data: dict[str, object] = {
        "kind": "issuer_record",
        "url": "",
        "status": "verified",
        "verification_method": "database",
        "confidence": 1.0,
        "official": True,
        "discovered_by": "system",
        "evidence": {"issuer_name": "Idempotent Issuer"},
    }
    gap_data: dict[str, object] = {
        "source_kind": None,
        "code": "test_idempotency_gap",
        "title": "Test gap",
        "level": "blocking",
        "requested_user_action": "None",
    }
    checkpoint = SourceDiscoveryCheckpoint(
        command=command,
        output={
            "stage": "source_discovery",
            "sources": [source_data],
            "gaps": [gap_data],
            "summary": "1 source, 1 gap.",
        },
    )

    runtime = ProductionCandidateRuntime(db=db_runtime)

    # Apply the same checkpoint twice
    await runtime.persist_candidate_sources_and_gaps(checkpoint)
    await runtime.persist_candidate_sources_and_gaps(checkpoint)

    async with db_runtime.session() as session:
        sources = (
            (
                await session.execute(
                    select(CandidateSourceRecord).where(
                        CandidateSourceRecord.candidate_id == candidate.id
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
                        CandidateGapRecord.candidate_id == candidate.id
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
                        CandidateEventRecord.candidate_id == candidate.id
                    )
                )
            )
            .scalars()
            .all()
        )

    assert len(sources) == 1, f"Expected 1 source, got {len(sources)}"
    assert len(gaps) <= 1, f"Duplicate gaps detected: {len(gaps)}"

    source_events = [e for e in events if e.event_type == "sources_persisted"]
    assert len(source_events) == 2, (
        f"Expected exactly 2 source_persisted events, got {len(source_events)}"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_http_client(
    *, status_code: int, content: bytes, final_url: str
) -> object:
    mock = AsyncMock(spec=SafeHttpClient)
    mock.get = AsyncMock(
        return_value=ValidatedHttpResponse(
            requested_url=final_url,
            final_url=final_url,
            status_code=status_code,
            headers={},
            content=content,
            redirect_chain=(),
            resolved_ips=(),
        )
    )
    return mock
