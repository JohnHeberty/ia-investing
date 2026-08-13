"""Integration tests for Candidate Intelligence — Application Service layer.

Tests the full flow through InvestmentCandidateApplicationService:
  candidate creation → source addition → gap resolution →
  exploration run → suggestion promotion/dismissal.

Uses a real PostgreSQL database (no mocked runtime).
Requires:
  docker compose --profile test up -d --wait
  pytest tests/integration/test_candidate_intelligence.py -x -v
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
import sqlalchemy as sa
from conftest import _postgres_reachable  # type: ignore[import-not-found]
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
from ia_investing.application.investment_candidates import (
    CandidateConcurrencyError,
    CandidateDuplicateError,
    CandidateIdempotencyConflictError,
    InvestmentCandidateApplicationService,
)
from ia_investing.candidate_intelligence.contracts import (
    CandidateCreateRequest,
    CandidateReanalysisRequest,
    CandidateSourceCreateRequest,
    ExplorationCreateRequest,
)
from ia_investing.candidate_intelligence.enums import CandidateStatus, SourceKind
from ia_investing.candidate_intelligence.readiness import DEFAULT_SOURCE_REQUIREMENTS
from ia_investing.platform.database.runtime import DatabaseRuntime

_SKIP_DB = pytest.mark.skipif(
    not _postgres_reachable(),
    reason="PostgreSQL not reachable — start with: docker compose --profile test up -d",
)

pytestmark = pytest.mark.integration

_DATA_AS_OF = datetime.now(UTC)
_PERMS = frozenset(
    {
        "candidates:create",
        "candidates:read",
        "candidates:update",
        "candidates:reanalyze",
        "research_cases:create",
        "research_cases:read",
        "research_cases:update",
        "exploration:create",
        "exploration:read",
        "exploration:update",
        "exploration:promote",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_org(session: AsyncSession) -> Organization:
    org = Organization(
        id=uuid4(),
        slug=f"ci-test-{uuid4().hex[:8]}",
        display_name="CI Test Org",
    )
    session.add(org)
    return org


def _make_issuer_instrument_listing(
    session: AsyncSession, *, ticker: str | None = None
) -> tuple[Issuer, Instrument, Listing]:
    if ticker is None:
        ticker = f"CI{uuid4().hex[:4].upper()}"
    issuer = Issuer(id=uuid4(), name_pt="CI Test Issuer S.A.", cnpj=f"{uuid4().hex[:8]}000199")
    session.add(issuer)
    instrument = Instrument(id=uuid4(), issuer_id=issuer.id, instrument_type="common_share")
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
async def db_runtime(engine: AsyncEngine) -> AsyncGenerator[DatabaseRuntime, None]:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield DatabaseRuntime(engine=engine, sessions=maker)


# ---------------------------------------------------------------------------
# 1. Candidate creation via Application Service
# ---------------------------------------------------------------------------


@_SKIP_DB
async def test_create_manual_candidate_persists_record(db_runtime: DatabaseRuntime) -> None:
    """create_manual creates a candidate, gap records, and an analysis run."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        await session.commit()

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        request = CandidateCreateRequest(ticker="Vale5", exchange="B3", rationale="Test creation")

        candidate, run, created = await svc.create_manual(
            organization_id=org_obj.id,
            actor_id="test-user",
            permissions=_PERMS,
            request=request,
            data_as_of=_DATA_AS_OF,
            idempotency_key=f"ci-{uuid4().hex[:8]}",
            correlation_id=uuid4(),
        )

    assert created is True
    assert candidate.ticker == "VALE5"
    assert candidate.exchange == "B3"
    assert candidate.status == CandidateStatus.IDENTITY_RESOLUTION.value
    assert candidate.lock_version == 1
    assert run.run_number == 1
    assert run.status == "queued"
    assert run.trigger == "initial"

    # Verify default gaps were created
    async with db_runtime.session() as session:
        gaps = (
            (
                await session.execute(
                    sa.select(CandidateGapRecord).where(CandidateGapRecord.candidate_id == candidate.id)
                )
            )
            .scalars()
            .all()
        )
    assert len(gaps) == len(DEFAULT_SOURCE_REQUIREMENTS)
    assert all(g.status == "open" for g in gaps)

    # Verify event was recorded
    async with db_runtime.session() as session:
        events = (
            (
                await session.execute(
                    sa.select(CandidateEventRecord).where(CandidateEventRecord.candidate_id == candidate.id)
                )
            )
            .scalars()
            .all()
        )
    assert any(e.event_type == "investment_candidate.created" for e in events)


@_SKIP_DB
async def test_create_manual_duplicate_ticker_raises(db_runtime: DatabaseRuntime) -> None:
    """Creating a second active candidate with the same ticker raises DuplicateError."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        await session.commit()

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        request = CandidateCreateRequest(ticker="MGLU3", exchange="B3")

        await svc.create_manual(
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            request=request,
            data_as_of=_DATA_AS_OF,
            idempotency_key=f"dup-{uuid4().hex[:8]}",
            correlation_id=uuid4(),
        )

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        with pytest.raises(CandidateDuplicateError, match="MGLU3"):
            await svc.create_manual(
                organization_id=org_obj.id,
                actor_id="test",
                permissions=_PERMS,
                request=request,
                data_as_of=_DATA_AS_OF,
                idempotency_key=f"dup2-{uuid4().hex[:8]}",
                correlation_id=uuid4(),
            )


@_SKIP_DB
async def test_create_manual_idempotency_replay(db_runtime: DatabaseRuntime) -> None:
    """Same idempotency key returns existing candidate (replayed=False)."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        await session.commit()

    ikey = f"idem-{uuid4().hex[:8]}"
    request = CandidateCreateRequest(ticker="ITUB4", exchange="B3")

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        c1, r1, created1 = await svc.create_manual(
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            request=request,
            data_as_of=_DATA_AS_OF,
            idempotency_key=ikey,
            correlation_id=uuid4(),
        )
    assert created1 is True

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        c2, r2, created2 = await svc.create_manual(
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            request=request,
            data_as_of=_DATA_AS_OF,
            idempotency_key=ikey,
            correlation_id=uuid4(),
        )
    assert created2 is False
    assert c1.id == c2.id
    assert r1.id == r2.id


@_SKIP_DB
async def test_create_manual_idempotency_conflict(db_runtime: DatabaseRuntime) -> None:
    """Same idempotency key with different payload raises ConflictError."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        await session.commit()

    ikey = f"conflict-{uuid4().hex[:8]}"

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        await svc.create_manual(
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            request=CandidateCreateRequest(ticker="BBAS3", exchange="B3"),
            data_as_of=_DATA_AS_OF,
            idempotency_key=ikey,
            correlation_id=uuid4(),
        )

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        with pytest.raises(CandidateIdempotencyConflictError):
            await svc.create_manual(
                organization_id=org_obj.id,
                actor_id="test",
                permissions=_PERMS,
                request=CandidateCreateRequest(ticker="BBDC4", exchange="B3"),
                data_as_of=_DATA_AS_OF,
                idempotency_key=ikey,
                correlation_id=uuid4(),
            )


@_SKIP_DB
async def test_create_manual_permission_denied(db_runtime: DatabaseRuntime) -> None:
    """create_manual raises PermissionError without required permission."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        await session.commit()

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        with pytest.raises(PermissionError, match="candidates:create"):
            await svc.create_manual(
                organization_id=org_obj.id,
                actor_id="test",
                permissions=frozenset(),
                request=CandidateCreateRequest(ticker="WEGE3", exchange="B3"),
                data_as_of=_DATA_AS_OF,
                idempotency_key=f"no-perm-{uuid4().hex[:8]}",
                correlation_id=uuid4(),
            )


# ---------------------------------------------------------------------------
# 2. Source addition
# ---------------------------------------------------------------------------


@_SKIP_DB
async def test_add_source_creates_record_and_event(db_runtime: DatabaseRuntime) -> None:
    """add_source persists a source and records an event."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        await session.commit()

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        candidate, _, _ = await svc.create_manual(
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            request=CandidateCreateRequest(ticker="RENT3", exchange="B3"),
            data_as_of=_DATA_AS_OF,
            idempotency_key=f"src-{uuid4().hex[:8]}",
            correlation_id=uuid4(),
        )

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        source = await svc.add_source(
            candidate_id=candidate.id,
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            request=CandidateSourceCreateRequest(
                kind=SourceKind.INVESTOR_RELATIONS,
                url="https://ri.rent3.com.br",
                notes="User-provided IR URL",
            ),
            expected_version=candidate.lock_version,
            correlation_id=uuid4(),
        )

    assert source.kind == SourceKind.INVESTOR_RELATIONS.value
    assert source.status == "discovered"
    assert source.verification_method == "user_confirmed"
    assert source.confidence == Decimal("0.7000")
    assert source.official is False
    assert source.url.startswith("https://ri.rent3.com.br")

    async with db_runtime.session() as session:
        events = (
            (
                await session.execute(
                    sa.select(CandidateEventRecord).where(
                        CandidateEventRecord.candidate_id == candidate.id,
                        CandidateEventRecord.event_type == "investment_candidate.source_supplied",
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(events) >= 1


@_SKIP_DB
async def test_add_source_duplicate_returns_existing(db_runtime: DatabaseRuntime) -> None:
    """Adding the same source twice returns the existing record (idempotent)."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        await session.commit()

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        candidate, _, _ = await svc.create_manual(
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            request=CandidateCreateRequest(ticker="SUZB3", exchange="B3"),
            data_as_of=_DATA_AS_OF,
            idempotency_key=f"src-dup-{uuid4().hex[:8]}",
            correlation_id=uuid4(),
        )

    req = CandidateSourceCreateRequest(kind=SourceKind.COMPANY_WEBSITE, url="https://www.suzano.com.br")

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        s1 = await svc.add_source(
            candidate_id=candidate.id,
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            request=req,
            expected_version=candidate.lock_version,
            correlation_id=uuid4(),
        )

    # Re-read candidate to get updated lock_version
    async with db_runtime.session() as session:
        updated_candidate = await session.get(InvestmentCandidateRecord, candidate.id)
        assert updated_candidate is not None

        svc = InvestmentCandidateApplicationService(session)
        s2 = await svc.add_source(
            candidate_id=candidate.id,
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            request=req,
            expected_version=updated_candidate.lock_version,
            correlation_id=uuid4(),
        )
    assert s1.id == s2.id


@_SKIP_DB
async def test_add_source_concurrency_conflict(db_runtime: DatabaseRuntime) -> None:
    """add_source raises ConcurrencyError when lock_version doesn't match."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        await session.commit()

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        candidate, _, _ = await svc.create_manual(
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            request=CandidateCreateRequest(ticker="JBSS3", exchange="B3"),
            data_as_of=_DATA_AS_OF,
            idempotency_key=f"conc-{uuid4().hex[:8]}",
            correlation_id=uuid4(),
        )

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        with pytest.raises(CandidateConcurrencyError):
            await svc.add_source(
                candidate_id=candidate.id,
                organization_id=org_obj.id,
                actor_id="test",
                permissions=_PERMS,
                request=CandidateSourceCreateRequest(
                    kind=SourceKind.CVM_PROFILE,
                    url="https://www.cvm.gov.br/jbss3",
                ),
                expected_version=999,
                correlation_id=uuid4(),
            )


# ---------------------------------------------------------------------------
# 3. Gap resolution
# ---------------------------------------------------------------------------


@_SKIP_DB
async def test_resolve_gap_marks_resolved(db_runtime: DatabaseRuntime) -> None:
    """resolve_gap marks an open gap as resolved with metadata."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        await session.commit()

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        candidate, _, _ = await svc.create_manual(
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            request=CandidateCreateRequest(ticker="ABEV3", exchange="B3"),
            data_as_of=_DATA_AS_OF,
            idempotency_key=f"gap-{uuid4().hex[:8]}",
            correlation_id=uuid4(),
        )

    async with db_runtime.session() as session:
        gaps = (
            (
                await session.execute(
                    sa.select(CandidateGapRecord).where(CandidateGapRecord.candidate_id == candidate.id)
                )
            )
            .scalars()
            .all()
        )
        target_gap = gaps[0]

        svc = InvestmentCandidateApplicationService(session)
        resolved_gap = await svc.resolve_gap(
            candidate_id=candidate.id,
            gap_id=target_gap.id,
            organization_id=org_obj.id,
            actor_id="test-user",
            permissions=_PERMS,
            notes="Source verified manually",
            expected_version=candidate.lock_version,
        )

    assert resolved_gap.status == "resolved"
    assert resolved_gap.resolved_by == "test-user"
    assert resolved_gap.resolution_notes == "Source verified manually"
    assert resolved_gap.resolved_at is not None


@_SKIP_DB
async def test_resolve_nonexistent_gap_raises(db_runtime: DatabaseRuntime) -> None:
    """resolve_gap raises LookupError for non-existent gap_id."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        await session.commit()

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        candidate, _, _ = await svc.create_manual(
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            request=CandidateCreateRequest(ticker="CPLE6", exchange="B3"),
            data_as_of=_DATA_AS_OF,
            idempotency_key=f"gap-nf-{uuid4().hex[:8]}",
            correlation_id=uuid4(),
        )

        with pytest.raises(LookupError):
            await svc.resolve_gap(
                candidate_id=candidate.id,
                gap_id=uuid4(),
                organization_id=org_obj.id,
                actor_id="test",
                permissions=_PERMS,
                notes="N/A",
                expected_version=candidate.lock_version,
            )


@_SKIP_DB
async def test_resolve_already_resolved_gap_raises(db_runtime: DatabaseRuntime) -> None:
    """resolve_gap raises ValueError when gap is already resolved."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        await session.commit()

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        candidate, _, _ = await svc.create_manual(
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            request=CandidateCreateRequest(ticker="ELET6", exchange="B3"),
            data_as_of=_DATA_AS_OF,
            idempotency_key=f"gap-alr-{uuid4().hex[:8]}",
            correlation_id=uuid4(),
        )

        gaps = (
            (
                await session.execute(
                    sa.select(CandidateGapRecord).where(CandidateGapRecord.candidate_id == candidate.id)
                )
            )
            .scalars()
            .all()
        )
        gap = gaps[0]

        await svc.resolve_gap(
            candidate_id=candidate.id,
            gap_id=gap.id,
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            notes="First resolution",
            expected_version=candidate.lock_version,
        )

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        # After first resolve, the gap status changed. We need a fresh version.
        updated_candidate = await session.get(InvestmentCandidateRecord, candidate.id)
        assert updated_candidate is not None
        with pytest.raises(ValueError, match="only open gaps"):
            await svc.resolve_gap(
                candidate_id=candidate.id,
                gap_id=gap.id,
                organization_id=org_obj.id,
                actor_id="test",
                permissions=_PERMS,
                notes="Second resolution attempt",
                expected_version=updated_candidate.lock_version,
            )


# ---------------------------------------------------------------------------
# 4. Reanalysis
# ---------------------------------------------------------------------------


@_SKIP_DB
async def test_request_reanalysis_creates_new_run(db_runtime: DatabaseRuntime) -> None:
    """request_reanalysis creates a new analysis run with incremented run_number."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        await session.commit()

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        candidate, _, _ = await svc.create_manual(
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            request=CandidateCreateRequest(ticker="LREN3", exchange="B3"),
            data_as_of=_DATA_AS_OF,
            idempotency_key=f"rean-{uuid4().hex[:8]}",
            correlation_id=uuid4(),
        )

    # Resolve all blocking gaps
    async with db_runtime.session() as session:
        gaps = (
            (
                await session.execute(
                    sa.select(CandidateGapRecord).where(CandidateGapRecord.candidate_id == candidate.id)
                )
            )
            .scalars()
            .all()
        )
        for gap in gaps:
            gap.status = "resolved"
            gap.resolved_at = datetime.now(UTC)
            gap.resolved_by = "test"
            gap.resolution_notes = "Auto-resolved"
        await session.commit()

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        updated_candidate = await session.get(InvestmentCandidateRecord, candidate.id)
        assert updated_candidate is not None

        run2 = await svc.request_reanalysis(
            candidate_id=candidate.id,
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            request=CandidateReanalysisRequest(
                data_as_of=_DATA_AS_OF,
                allow_incomplete=True,
            ),
            expected_version=updated_candidate.lock_version,
            correlation_id=uuid4(),
        )

    assert run2.run_number == 2
    assert run2.trigger == "manual_retry"
    assert run2.status == "queued"


@_SKIP_DB
async def test_request_reanalysis_rejects_when_blocked(db_runtime: DatabaseRuntime) -> None:
    """request_reanalysis raises ValueError when blocking gaps exist and allow_incomplete=False."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        await session.commit()

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        candidate, _, _ = await svc.create_manual(
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            request=CandidateCreateRequest(ticker="PETZ3", exchange="B3"),
            data_as_of=_DATA_AS_OF,
            idempotency_key=f"rean-blk-{uuid4().hex[:8]}",
            correlation_id=uuid4(),
        )

        with pytest.raises(ValueError, match="blocking gaps"):
            await svc.request_reanalysis(
                candidate_id=candidate.id,
                organization_id=org_obj.id,
                actor_id="test",
                permissions=_PERMS,
                request=CandidateReanalysisRequest(
                    data_as_of=_DATA_AS_OF,
                    allow_incomplete=False,
                ),
                expected_version=candidate.lock_version,
                correlation_id=uuid4(),
            )


# ---------------------------------------------------------------------------
# 5. Exploration run creation
# ---------------------------------------------------------------------------


@_SKIP_DB
async def test_create_exploration_run_persists(db_runtime: DatabaseRuntime) -> None:
    """create_exploration_run persists a new exploration run record."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        await session.commit()

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        run = await svc.create_exploration_run(
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            request=ExplorationCreateRequest(
                strategy_codes=("momentum", "value"),
                data_as_of=_DATA_AS_OF,
                minimum_liquidity=Decimal("1000000"),
                maximum_suggestions=20,
            ),
            correlation_id=uuid4(),
        )

    assert run.status == "queued"
    assert run.strategy_codes == ["momentum", "value"]
    assert run.minimum_liquidity == Decimal("1000000")
    assert run.maximum_suggestions == 20
    assert run.universe_size == 0


@_SKIP_DB
async def test_list_exploration_runs(db_runtime: DatabaseRuntime) -> None:
    """list_exploration_runs returns runs for the given organization."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        await session.commit()

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        await svc.create_exploration_run(
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            request=ExplorationCreateRequest(
                strategy_codes=("momentum",),
                data_as_of=_DATA_AS_OF,
                minimum_liquidity=Decimal("500000"),
                maximum_suggestions=10,
            ),
            correlation_id=uuid4(),
        )

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        runs = await svc.list_exploration_runs(
            organization_id=org_obj.id,
            permissions=_PERMS,
            status=None,
            limit=10,
        )
    assert len(runs) == 1
    assert runs[0].status == "queued"


# ---------------------------------------------------------------------------
# 6. Suggestion promotion/dismissal
# ---------------------------------------------------------------------------


@_SKIP_DB
async def test_promote_suggestion_creates_candidate(db_runtime: DatabaseRuntime) -> None:
    """promote_suggestion creates a new candidate from an exploration suggestion."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        issuer, instrument, listing = _make_issuer_instrument_listing(session)
        run = ExplorationRunRecord(
            id=uuid4(),
            organization_id=org_obj.id,
            status="succeeded",
            strategy_codes=["momentum"],
            requested_by="test",
            data_as_of=_DATA_AS_OF,
            minimum_liquidity=Decimal("1000000"),
            maximum_suggestions=10,
        )
        session.add(run)
        suggestion = ExplorationSuggestionRecord(
            id=uuid4(),
            exploration_run_id=run.id,
            organization_id=org_obj.id,
            instrument_id=instrument.id,
            issuer_id=issuer.id,
            ticker=listing.ticker,
            exchange="B3",
            status="new",
            quantitative_score=Decimal("0.8500"),
            data_coverage_score=Decimal("0.7000"),
            source_discovery_score=Decimal("0.6000"),
            rationale="Momentum candidate with strong signals",
            signals=["price_breakout"],
            risks=["sector_risk"],
            source_snapshot=[
                {
                    "kind": "company_website",
                    "url": "https://www.prom4.com.br",
                    "status": "discovered",
                    "verification_method": "agent_inference",
                    "confidence": "0.5000",
                }
            ],
        )
        session.add(suggestion)
        await session.commit()
        suggestion_id = suggestion.id
        org_id = org_obj.id

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        candidate = await svc.promote_suggestion(
            suggestion_id=suggestion_id,
            organization_id=org_id,
            actor_id="test-user",
            permissions=_PERMS,
            idempotency_key=f"prom-{uuid4().hex[:8]}",
            correlation_id=uuid4(),
        )

    assert candidate.ticker == listing.ticker
    assert candidate.origin == "explorer"
    assert candidate.status == CandidateStatus.SUGGESTED.value

    async with db_runtime.session() as session:
        refreshed_suggestion = await session.get(ExplorationSuggestionRecord, suggestion_id)
        assert refreshed_suggestion is not None
        assert refreshed_suggestion.status == "promoted"
        assert refreshed_suggestion.promoted_candidate_id == candidate.id

        gaps = (
            (
                await session.execute(
                    sa.select(CandidateGapRecord).where(CandidateGapRecord.candidate_id == candidate.id)
                )
            )
            .scalars()
            .all()
        )
        sources = (
            (
                await session.execute(
                    sa.select(CandidateSourceRecord).where(CandidateSourceRecord.candidate_id == candidate.id)
                )
            )
            .scalars()
            .all()
        )

    assert len(gaps) == len(DEFAULT_SOURCE_REQUIREMENTS)
    assert len(sources) == 1
    assert sources[0].kind == "company_website"


@_SKIP_DB
async def test_dismiss_suggestion_sets_status(db_runtime: DatabaseRuntime) -> None:
    """dismiss_suggestion marks a suggestion as dismissed with reason."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        issuer, instrument, listing = _make_issuer_instrument_listing(session)
        run = ExplorationRunRecord(
            id=uuid4(),
            organization_id=org_obj.id,
            status="succeeded",
            strategy_codes=["value"],
            requested_by="test",
            data_as_of=_DATA_AS_OF,
            minimum_liquidity=Decimal("1000000"),
            maximum_suggestions=10,
        )
        session.add(run)
        suggestion = ExplorationSuggestionRecord(
            id=uuid4(),
            exploration_run_id=run.id,
            organization_id=org_obj.id,
            instrument_id=instrument.id,
            issuer_id=issuer.id,
            ticker=listing.ticker,
            exchange="B3",
            status="new",
            quantitative_score=Decimal("0.6000"),
            data_coverage_score=Decimal("0.5000"),
            source_discovery_score=Decimal("0.4000"),
            rationale="Test dismissal",
            signals=[],
            risks=["low liquidity"],
        )
        session.add(suggestion)
        await session.commit()
        suggestion_id = suggestion.id
        org_id = org_obj.id

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        dismissed = await svc.dismiss_suggestion(
            suggestion_id=suggestion_id,
            organization_id=org_id,
            actor_id="test-user",
            permissions=_PERMS,
            reason="Low liquidity, does not meet investment criteria",
        )

    assert dismissed.status == "dismissed"
    assert dismissed.dismissed_by == "test-user"
    assert dismissed.dismissal_reason == "Low liquidity, does not meet investment criteria"
    assert dismissed.dismissed_at is not None


@_SKIP_DB
async def test_dismiss_nonexistent_suggestion_raises(db_runtime: DatabaseRuntime) -> None:
    """dismiss_suggestion raises LookupError for non-existent suggestion."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        await session.commit()

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        with pytest.raises(LookupError, match="not found"):
            await svc.dismiss_suggestion(
                suggestion_id=uuid4(),
                organization_id=org_obj.id,
                actor_id="test",
                permissions=_PERMS,
                reason="N/A",
            )


@_SKIP_DB
async def test_dismiss_already_dismissed_suggestion_raises(db_runtime: DatabaseRuntime) -> None:
    """dismiss_suggestion raises ValueError when suggestion is already dismissed."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        issuer, instrument, listing = _make_issuer_instrument_listing(session)
        run = ExplorationRunRecord(
            id=uuid4(),
            organization_id=org_obj.id,
            status="succeeded",
            strategy_codes=["value"],
            requested_by="test",
            data_as_of=_DATA_AS_OF,
            minimum_liquidity=Decimal("1000000"),
            maximum_suggestions=10,
        )
        session.add(run)
        suggestion = ExplorationSuggestionRecord(
            id=uuid4(),
            exploration_run_id=run.id,
            organization_id=org_obj.id,
            instrument_id=instrument.id,
            issuer_id=issuer.id,
            ticker=listing.ticker,
            exchange="B3",
            status="new",
            quantitative_score=Decimal("0.6000"),
            data_coverage_score=Decimal("0.5000"),
            source_discovery_score=Decimal("0.4000"),
            rationale="Test double dismiss",
            signals=[],
            risks=[],
        )
        session.add(suggestion)
        await session.commit()
        suggestion_id = suggestion.id
        org_id = org_obj.id

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        await svc.dismiss_suggestion(
            suggestion_id=suggestion_id,
            organization_id=org_id,
            actor_id="test",
            permissions=_PERMS,
            reason="First dismissal",
        )

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        with pytest.raises(ValueError, match="only new"):
            await svc.dismiss_suggestion(
                suggestion_id=suggestion_id,
                organization_id=org_id,
                actor_id="test",
                permissions=_PERMS,
                reason="Second dismissal attempt",
            )


@_SKIP_DB
async def test_promote_duplicate_ticker_returns_existing(db_runtime: DatabaseRuntime) -> None:
    """promote_suggestion returns the existing candidate if ticker already exists."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        issuer, instrument, listing = _make_issuer_instrument_listing(session)
        run = ExplorationRunRecord(
            id=uuid4(),
            organization_id=org_obj.id,
            status="succeeded",
            strategy_codes=["momentum"],
            requested_by="test",
            data_as_of=_DATA_AS_OF,
            minimum_liquidity=Decimal("1000000"),
            maximum_suggestions=10,
        )
        session.add(run)
        suggestion = ExplorationSuggestionRecord(
            id=uuid4(),
            exploration_run_id=run.id,
            organization_id=org_obj.id,
            instrument_id=instrument.id,
            issuer_id=issuer.id,
            ticker=listing.ticker,
            exchange="B3",
            status="new",
            quantitative_score=Decimal("0.8000"),
            data_coverage_score=Decimal("0.7000"),
            source_discovery_score=Decimal("0.6000"),
            rationale="Duplicate ticker test",
            signals=[],
            risks=[],
        )
        session.add(suggestion)
        await session.commit()
        suggestion_id = suggestion.id
        org_id = org_obj.id

    # Create an existing candidate with the same ticker
    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        existing_candidate, _, _ = await svc.create_manual(
            organization_id=org_id,
            actor_id="test",
            permissions=_PERMS,
            request=CandidateCreateRequest(ticker=listing.ticker, exchange="B3"),
            data_as_of=_DATA_AS_OF,
            idempotency_key=f"existing-{uuid4().hex[:8]}",
            correlation_id=uuid4(),
        )

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        result = await svc.promote_suggestion(
            suggestion_id=suggestion_id,
            organization_id=org_id,
            actor_id="test",
            permissions=_PERMS,
            idempotency_key=f"prom-dup-{uuid4().hex[:8]}",
            correlation_id=uuid4(),
        )

    assert result.id == existing_candidate.id

    async with db_runtime.session() as session:
        refreshed_suggestion = await session.get(ExplorationSuggestionRecord, suggestion_id)
        assert refreshed_suggestion is not None
        assert refreshed_suggestion.status == "duplicate"


# ---------------------------------------------------------------------------
# 7. List candidates
# ---------------------------------------------------------------------------


@_SKIP_DB
async def test_list_candidates_returns_org_scoped(db_runtime: DatabaseRuntime) -> None:
    """list_candidates only returns candidates for the given organization."""
    async with db_runtime.session() as session:
        org1 = _make_org(session)
        org2 = _make_org(session)
        await session.commit()

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        await svc.create_manual(
            organization_id=org1.id,
            actor_id="test",
            permissions=_PERMS,
            request=CandidateCreateRequest(ticker="LIST1", exchange="B3"),
            data_as_of=_DATA_AS_OF,
            idempotency_key=f"list1-{uuid4().hex[:8]}",
            correlation_id=uuid4(),
        )
        await svc.create_manual(
            organization_id=org2.id,
            actor_id="test",
            permissions=_PERMS,
            request=CandidateCreateRequest(ticker="LIST2", exchange="B3"),
            data_as_of=_DATA_AS_OF,
            idempotency_key=f"list2-{uuid4().hex[:8]}",
            correlation_id=uuid4(),
        )

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        candidates_org1 = await svc.list_candidates(
            organization_id=org1.id,
            permissions=_PERMS,
            status=None,
            after=None,
            limit=50,
        )
    assert len(candidates_org1) == 1
    assert candidates_org1[0].ticker == "LIST1"


@_SKIP_DB
async def test_list_candidates_filter_by_status(db_runtime: DatabaseRuntime) -> None:
    """list_candidates filters by status when provided."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        await session.commit()

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        await svc.create_manual(
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            request=CandidateCreateRequest(ticker="FILT4", exchange="B3"),
            data_as_of=_DATA_AS_OF,
            idempotency_key=f"filt-{uuid4().hex[:8]}",
            correlation_id=uuid4(),
        )

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        approved = await svc.list_candidates(
            organization_id=org_obj.id,
            permissions=_PERMS,
            status=CandidateStatus.APPROVED.value,
            after=None,
            limit=50,
        )
        pending = await svc.list_candidates(
            organization_id=org_obj.id,
            permissions=_PERMS,
            status=CandidateStatus.IDENTITY_RESOLUTION.value,
            after=None,
            limit=50,
        )
    assert len(approved) == 0
    assert len(pending) == 1


# ---------------------------------------------------------------------------
# 8. Get candidate detail
# ---------------------------------------------------------------------------


@_SKIP_DB
async def test_get_detail_returns_full_payload(db_runtime: DatabaseRuntime) -> None:
    """get_detail returns candidate with sources, gaps, runs, and events."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        await session.commit()

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        candidate, run, _ = await svc.create_manual(
            organization_id=org_obj.id,
            actor_id="test",
            permissions=_PERMS,
            request=CandidateCreateRequest(ticker="DTAIL", exchange="B3"),
            data_as_of=_DATA_AS_OF,
            idempotency_key=f"detail-{uuid4().hex[:8]}",
            correlation_id=uuid4(),
        )

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        detail = await svc.get_detail(
            candidate_id=candidate.id,
            organization_id=org_obj.id,
            permissions=_PERMS,
        )

    assert detail is not None
    assert detail.candidate.id == candidate.id
    assert len(detail.gaps) == len(DEFAULT_SOURCE_REQUIREMENTS)
    assert len(detail.runs) == 1
    assert detail.runs[0].id == run.id
    assert len(detail.events) >= 1


@_SKIP_DB
async def test_get_detail_returns_none_for_nonexistent(db_runtime: DatabaseRuntime) -> None:
    """get_detail returns None when candidate doesn't exist."""
    async with db_runtime.session() as session:
        org_obj = _make_org(session)
        await session.commit()

    async with db_runtime.session() as session:
        svc = InvestmentCandidateApplicationService(session)
        detail = await svc.get_detail(
            candidate_id=uuid4(),
            organization_id=org_obj.id,
            permissions=_PERMS,
        )
    assert detail is None


# ---------------------------------------------------------------------------
# 9. Pipeline execution (sync) — via ProductionCandidateRuntime
# ---------------------------------------------------------------------------


@_SKIP_DB
async def test_pipeline_identity_resolution_succeeds(engine: AsyncEngine) -> None:
    """Pipeline stage 1 (identity resolution) succeeds with a known ticker."""
    from ia_investing.integrations.production_runtime import ProductionCandidateRuntime
    from ia_investing.orchestration.activities.candidate_intelligence import CandidateWorkflowInput

    ticker = f"P{uuid4().hex[:4].upper()}"
    maker = async_sessionmaker(engine, expire_on_commit=False)
    db = DatabaseRuntime(engine=engine, sessions=maker)

    async with db.session() as session:
        org = Organization(id=uuid4(), slug=f"pipe-{uuid4().hex[:8]}", display_name="Pipeline Test")
        session.add(org)
        issuer = Issuer(id=uuid4(), name_pt="Pipeline Issuer S.A.", cnpj=f"{uuid4().hex[:8]}000199")
        session.add(issuer)
        instrument = Instrument(id=uuid4(), issuer_id=issuer.id, instrument_type="common_share")
        session.add(instrument)
        listing = Listing(
            id=uuid4(),
            instrument_id=instrument.id,
            exchange_code="B3",
            ticker=ticker,
            valid_from=date(2020, 1, 1),
        )
        session.add(listing)
        candidate = InvestmentCandidateRecord(
            id=uuid4(),
            organization_id=org.id,
            origin="manual",
            status="identity_resolution",
            ticker=ticker,
            exchange="B3",
            created_by="test",
            idempotency_key=f"pipe-{uuid4().hex[:8]}",
            request_hash=hashlib.sha256(uuid4().bytes).hexdigest(),
            lock_version=1,
        )
        session.add(candidate)
        run = CandidateAnalysisRunRecord(
            id=uuid4(),
            candidate_id=candidate.id,
            run_number=1,
            trigger="manual",
            status="running",
            requested_by="test",
            data_as_of=datetime.now(UTC),
        )
        session.add(run)
        await session.commit()

    command = CandidateWorkflowInput(
        candidate_id=candidate.id,
        analysis_run_id=run.id,
        organization_id=org.id,
        data_as_of=datetime.now(UTC),
    )
    runtime = ProductionCandidateRuntime(db=db)

    checkpoint = await runtime.resolve_candidate_identity(command)
    assert checkpoint.blocked is False
    assert checkpoint.stage == "identity_resolution"
    assert checkpoint.decision == "continue"

    async with db.session() as session:
        updated = await session.get(InvestmentCandidateRecord, candidate.id)
        assert updated is not None
    assert updated.issuer_id == issuer.id
    assert updated.instrument_id == instrument.id


@_SKIP_DB
async def test_pipeline_source_discovery_finds_sources(engine: AsyncEngine) -> None:
    """Pipeline stage 2 (source discovery) finds B3 and issuer sources."""
    from ia_investing.integrations.production_runtime import ProductionCandidateRuntime
    from ia_investing.orchestration.activities.candidate_intelligence import CandidateWorkflowInput

    ticker = f"D{uuid4().hex[:4].upper()}"
    maker = async_sessionmaker(engine, expire_on_commit=False)
    db = DatabaseRuntime(engine=engine, sessions=maker)

    async with db.session() as session:
        org = Organization(id=uuid4(), slug=f"disc-{uuid4().hex[:8]}", display_name="Discovery Test")
        session.add(org)
        issuer = Issuer(id=uuid4(), name_pt="Discovery Issuer S.A.", cnpj=f"{uuid4().hex[:8]}000199")
        session.add(issuer)
        instrument = Instrument(id=uuid4(), issuer_id=issuer.id, instrument_type="common_share")
        session.add(instrument)
        listing = Listing(
            id=uuid4(),
            instrument_id=instrument.id,
            exchange_code="B3",
            ticker=ticker,
            valid_from=date(2020, 1, 1),
        )
        session.add(listing)
        candidate = InvestmentCandidateRecord(
            id=uuid4(),
            organization_id=org.id,
            origin="manual",
            status="source_discovery",
            ticker=ticker,
            exchange="B3",
            issuer_id=issuer.id,
            instrument_id=instrument.id,
            created_by="test",
            idempotency_key=f"disc-{uuid4().hex[:8]}",
            request_hash=hashlib.sha256(uuid4().bytes).hexdigest(),
            lock_version=1,
        )
        session.add(candidate)
        run = CandidateAnalysisRunRecord(
            id=uuid4(),
            candidate_id=candidate.id,
            run_number=1,
            trigger="manual",
            status="running",
            requested_by="test",
            data_as_of=datetime.now(UTC),
        )
        session.add(run)
        await session.commit()

    command = CandidateWorkflowInput(
        candidate_id=candidate.id,
        analysis_run_id=run.id,
        organization_id=org.id,
        data_as_of=datetime.now(UTC),
    )
    runtime = ProductionCandidateRuntime(db=db)

    discovery = await runtime.discover_candidate_sources(command)
    assert discovery is not None
    output = discovery.output
    assert output["stage"] == "source_discovery"
    sources = output.get("sources", [])
    assert len(sources) >= 2, f"Expected >= 2 sources, got {len(sources)}"

    source_kinds = {s.get("kind") for s in sources}
    assert "b3_listing" in source_kinds
    assert "issuer_record" in source_kinds


@_SKIP_DB
async def test_pipeline_persist_and_evaluate_readiness(engine: AsyncEngine) -> None:
    """Persisting sources and evaluating readiness works end-to-end."""
    from ia_investing.integrations.production_runtime import ProductionCandidateRuntime
    from ia_investing.orchestration.activities.candidate_intelligence import (
        CandidateWorkflowInput,
        SourceDiscoveryCheckpoint,
    )

    ticker = f"R{uuid4().hex[:4].upper()}"
    maker = async_sessionmaker(engine, expire_on_commit=False)
    db = DatabaseRuntime(engine=engine, sessions=maker)

    async with db.session() as session:
        org = Organization(id=uuid4(), slug=f"read-{uuid4().hex[:8]}", display_name="Readiness Test")
        session.add(org)
        issuer = Issuer(id=uuid4(), name_pt="Readiness Issuer S.A.", cnpj=f"{uuid4().hex[:8]}000199")
        session.add(issuer)
        instrument = Instrument(id=uuid4(), issuer_id=issuer.id, instrument_type="common_share")
        session.add(instrument)
        listing = Listing(
            id=uuid4(),
            instrument_id=instrument.id,
            exchange_code="B3",
            ticker=ticker,
            valid_from=date(2020, 1, 1),
        )
        session.add(listing)
        candidate = InvestmentCandidateRecord(
            id=uuid4(),
            organization_id=org.id,
            origin="manual",
            status="source_discovery",
            ticker=ticker,
            exchange="B3",
            issuer_id=issuer.id,
            instrument_id=instrument.id,
            cnpj=issuer.cnpj,
            created_by="test",
            idempotency_key=f"read-{uuid4().hex[:8]}",
            request_hash=hashlib.sha256(uuid4().bytes).hexdigest(),
            lock_version=1,
        )
    """Persisting sources and evaluating readiness works end-to-end."""

    maker = async_sessionmaker(engine, expire_on_commit=False)
    db = DatabaseRuntime(engine=engine, sessions=maker)

    async with db.session() as session:
        org = Organization(id=uuid4(), slug=f"read-{uuid4().hex[:8]}", display_name="Readiness Test")
        session.add(org)
        issuer = Issuer(id=uuid4(), name_pt="Readiness Issuer S.A.", cnpj=f"{uuid4().hex[:8]}000199")
        session.add(issuer)
        instrument = Instrument(id=uuid4(), issuer_id=issuer.id, instrument_type="common_share")
        session.add(instrument)
        listing = Listing(
            id=uuid4(),
            instrument_id=instrument.id,
            exchange_code="B3",
            ticker="READ4",
            valid_from=date(2020, 1, 1),
        )
        session.add(listing)
        candidate = InvestmentCandidateRecord(
            id=uuid4(),
            organization_id=org.id,
            origin="manual",
            status="source_discovery",
            ticker="READ4",
            exchange="B3",
            issuer_id=issuer.id,
            instrument_id=instrument.id,
            cnpj=issuer.cnpj,
            created_by="test",
            idempotency_key=f"read-{uuid4().hex[:8]}",
            request_hash=hashlib.sha256(uuid4().bytes).hexdigest(),
            lock_version=1,
        )
        session.add(candidate)
        run = CandidateAnalysisRunRecord(
            id=uuid4(),
            candidate_id=candidate.id,
            run_number=1,
            trigger="manual",
            status="running",
            requested_by="test",
            data_as_of=datetime.now(UTC),
        )
        session.add(run)
        await session.commit()

    command = CandidateWorkflowInput(
        candidate_id=candidate.id,
        analysis_run_id=run.id,
        organization_id=org.id,
        data_as_of=datetime.now(UTC),
    )
    runtime = ProductionCandidateRuntime(db=db)

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
                    "evidence": {"issuer_name": "Readiness Issuer S.A."},
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
                    "title": "IR page not found",
                    "level": "blocking",
                    "requested_user_action": "Provide IR URL",
                    "source_kind": "investor_relations",
                }
            ],
            "summary": "2 sources, 1 gap.",
        },
    )

    await runtime.persist_candidate_sources_and_gaps(checkpoint)

    async with db.session() as session:
        sources = (
            (
                await session.execute(
                    sa.select(CandidateSourceRecord).where(CandidateSourceRecord.candidate_id == candidate.id)
                )
            )
            .scalars()
            .all()
        )
        gaps = (
            (
                await session.execute(
                    sa.select(CandidateGapRecord).where(CandidateGapRecord.candidate_id == candidate.id)
                )
            )
            .scalars()
            .all()
        )

    assert len(sources) == 2
    assert len(gaps) == 1
    assert gaps[0].code == "investor_relations_missing"

    readiness = await runtime.evaluate_candidate_readiness(command)
    assert readiness.blocked is True
    assert "investor_relations_missing" in readiness.blocker_codes


@_SKIP_DB
async def test_pipeline_complete_run_succeeds(engine: AsyncEngine) -> None:
    """complete_candidate_analysis_run marks run as succeeded."""
    from ia_investing.integrations.production_runtime import ProductionCandidateRuntime
    from ia_investing.orchestration.activities.candidate_intelligence import (
        CandidateCheckpoint,
        CandidateWorkflowInput,
    )

    maker = async_sessionmaker(engine, expire_on_commit=False)
    db = DatabaseRuntime(engine=engine, sessions=maker)

    async with db.session() as session:
        org = Organization(id=uuid4(), slug=f"comp-{uuid4().hex[:8]}", display_name="Complete Test")
        session.add(org)
        candidate = InvestmentCandidateRecord(
            id=uuid4(),
            organization_id=org.id,
            origin="manual",
            status="committee_review",
            ticker="COMP4",
            exchange="B3",
            created_by="test",
            idempotency_key=f"comp-{uuid4().hex[:8]}",
            request_hash=hashlib.sha256(uuid4().bytes).hexdigest(),
            lock_version=1,
        )
        session.add(candidate)
        run = CandidateAnalysisRunRecord(
            id=uuid4(),
            candidate_id=candidate.id,
            run_number=1,
            trigger="manual",
            status="running",
            requested_by="test",
            data_as_of=datetime.now(UTC),
        )
        session.add(run)
        await session.commit()

    runtime = ProductionCandidateRuntime(db=db)
    command = CandidateWorkflowInput(
        candidate_id=candidate.id,
        analysis_run_id=run.id,
        organization_id=org.id,
        data_as_of=datetime.now(UTC),
    )
    checkpoint = CandidateCheckpoint(
        candidate_id=candidate.id,
        stage="committee_review",
        blocked=False,
        decision="approve",
        reason="All checks passed.",
    )

    result = await runtime.complete_candidate_analysis_run(command, checkpoint)
    assert result.status == "succeeded"
    assert result.decision == "approve"

    async with db.session() as session:
        updated_run = await session.get(CandidateAnalysisRunRecord, run.id)
        assert updated_run is not None
    assert updated_run.status == "succeeded"
    assert updated_run.completed_at is not None
    assert updated_run.decision == "approve"
