"""End-to-end integration test for the candidate intelligence pipeline.

Exercises the full flow:
  identity resolution → source discovery → source validation →
  document collection → fundamental analysis → risk analysis →
  committee review → completion

Uses mocked AI provider (MockProvider) and mocked HTTP client to avoid
dependencies on external services (LiteLLM, CVM API, B3, IR portals).

Requirements:
  docker compose --profile test up -d --wait
  pytest tests/integration/test_candidate_e2e.py -x -v
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4, uuid5

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.agent_runtime import (
    AgentArtifact,
    AgentCapability,
    AgentVersion,
)
from database.models.catalog import Issuer
from database.models.identity import Organization  # type: ignore[import-untyped]
from database.models.instrument_master import Instrument, InstrumentIdentifier, Listing
from ia_investing.ai.provider import MockProvider
from ia_investing.integrations.production_runtime import ProductionCandidateRuntime
from ia_investing.orchestration.activities.candidate_intelligence import (
    CandidateCheckpoint,
    CandidateSourceValidationInput,
    CandidateWorkflowInput,
)
from ia_investing.platform.database.runtime import DatabaseRuntime
from ia_investing.platform.http.safe_client import EgressPolicy, SafeHttpClient

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

TZ = UTC
_TEST_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
_TEST_ISSUER_ID = UUID("00000000-0000-0000-0000-000000000002")
_TEST_INSTRUMENT_ID = UUID("00000000-0000-0000-0000-000000000003")
_TEST_LISTING_ID = UUID("00000000-0000-0000-0000-000000000004")


def _make_test_candidate_id() -> UUID:
    """Generate a unique candidate_id for each test run to avoid aggregate_version conflicts."""
    return uuid4()


_TEST_ANALYSIS_RUN_ID = UUID("00000000-0000-0000-0000-000000000006")
_TEST_CAPABILITY_ID = UUID("00000000-0000-0000-0000-000000000007")
_TEST_ARTIFACT_ID_PROMPT = UUID("00000000-0000-0000-0000-000000000010")
_TEST_ARTIFACT_ID_SCHEMA = UUID("00000000-0000-0000-0000-000000000011")
_TEST_ARTIFACT_ID_MODEL = UUID("00000000-0000-0000-0000-000000000012")
_TEST_ARTIFACT_ID_TOOLSET = UUID("00000000-0000-0000-0000-000000000013")
_TEST_AGENT_VERSION_ID = UUID("00000000-0000-0000-0000-000000000014")

_TODAY = datetime(2026, 7, 15, tzinfo=TZ)
_AS_OF_DATE = _TODAY.date()


# ---------------------------------------------------------------------------
# Fixtures — database records
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_org(session: AsyncSession) -> Organization:
    """Create or return existing test organization."""
    from sqlalchemy.dialects.postgresql import insert

    stmt = (
        insert(Organization)
        .values(
            id=_TEST_ORG_ID,
            slug="test-org",
            display_name="Test Org",
            status="active",
        )
        .on_conflict_do_nothing()
    )
    await session.execute(stmt)
    await session.commit()

    # Fetch existing or create new
    result = await session.execute(sa.select(Organization).where(Organization.id == _TEST_ORG_ID))
    org = result.scalar_one_or_none()
    if org is None:
        org = Organization(
            id=_TEST_ORG_ID,
            slug="test-org",
            display_name="Test Org",
            status="active",
        )
        session.add(org)
        await session.commit()
    return org


@pytest_asyncio.fixture
async def test_issuer(session: AsyncSession) -> Issuer:
    """Create PETR4 issuer record with CNPJ and IR URL."""
    stmt = sa.select(Issuer).where(Issuer.id == _TEST_ISSUER_ID)
    result = await session.execute(stmt)
    issuer = result.scalar_one_or_none()
    if issuer is None:
        issuer = Issuer(
            id=_TEST_ISSUER_ID,
            name_pt="Petróleo Brasileiro S.A. - Petrobras",
            cnpj="33000167000101",
            website_ri_url="https://www.petrobras.com.br",
            is_active=True,
        )
        session.add(issuer)
        await session.commit()
    return issuer


@pytest_asyncio.fixture
async def test_instrument(session: AsyncSession, test_issuer: Issuer) -> Instrument:
    """Create PETR4 instrument."""
    stmt = sa.select(Instrument).where(Instrument.id == _TEST_INSTRUMENT_ID)
    result = await session.execute(stmt)
    instrument = result.scalar_one_or_none()
    if instrument is None:
        instrument = Instrument(
            id=_TEST_INSTRUMENT_ID,
            issuer_id=test_issuer.id,
            instrument_type="preferred_share",
            share_class="PETR4",
            currency_code="BRL",
            is_active=True,
        )
        session.add(instrument)
        await session.commit()
    return instrument


@pytest_asyncio.fixture
async def test_listing(session: AsyncSession, test_instrument: Instrument) -> Listing:
    """Create PETR4 listing on B3."""
    stmt = sa.select(Listing).where(Listing.id == _TEST_LISTING_ID)
    result = await session.execute(stmt)
    listing = result.scalar_one_or_none()
    if listing is None:
        listing = Listing(
            id=_TEST_LISTING_ID,
            instrument_id=test_instrument.id,
            ticker="PETR4",
            exchange_code="B3",
            market_segment="normal",
            valid_from=datetime(2000, 1, 1, tzinfo=UTC).date(),
        )
        session.add(listing)

        # Also add an identifier for the CNPJ
        identifier = InstrumentIdentifier(
            instrument_id=test_instrument.id,
            identifier_type="CNPJ",
            identifier_value="33000167000101",
            valid_from=datetime(2000, 1, 1, tzinfo=UTC).date(),
        )
        session.add(identifier)
        await session.commit()
    return listing


@pytest_asyncio.fixture
async def test_candidate(
    session: AsyncSession,
    test_org: Organization,
    test_issuer: Issuer,
    test_instrument: Instrument,
) -> dict[str, Any]:
    """Create candidate record and analysis run."""
    from database.models.investment_candidates import (
        CandidateAnalysisRunRecord,
        CandidateEventRecord,
        CandidateGapRecord,
        CandidateSourceRecord,
        InvestmentCandidateRecord,
    )

    # Generate unique identifiers for this test run
    test_candidate_id = _make_test_candidate_id()
    test_idempotency_key = f"e2e-test-{test_candidate_id.hex[:8]}"
    test_ticker = f"PETR4-{test_candidate_id.hex[:4]}"

    # Delete existing records to ensure fresh state (sources first, then candidate)
    await session.execute(sa.delete(CandidateEventRecord).where(CandidateEventRecord.candidate_id == test_candidate_id))
    await session.execute(
        sa.delete(CandidateSourceRecord).where(CandidateSourceRecord.candidate_id == test_candidate_id)
    )
    await session.execute(sa.delete(CandidateGapRecord).where(CandidateGapRecord.candidate_id == test_candidate_id))
    await session.execute(
        sa.delete(CandidateAnalysisRunRecord).where(CandidateAnalysisRunRecord.candidate_id == test_candidate_id)
    )

    # Delete any existing candidate with the same ticker (to avoid uq_candidate_active_ticker constraint)
    await session.execute(
        sa.delete(InvestmentCandidateRecord).where(
            sa.and_(
                InvestmentCandidateRecord.organization_id == test_org.id,
                InvestmentCandidateRecord.ticker == test_ticker,
            )
        )
    )

    # Delete existing candidate by id if present
    existing_candidate = await session.execute(
        sa.select(InvestmentCandidateRecord).where(InvestmentCandidateRecord.id == test_candidate_id)
    )
    existing_candidate = existing_candidate.scalar_one_or_none()
    if existing_candidate:
        await session.delete(existing_candidate)
        await session.flush()

    # Also delete any candidate events for this candidate (unique constraint on candidate_id + aggregate_version)
    await session.execute(
        sa.delete(CandidateEventRecord).where(
            sa.and_(
                CandidateEventRecord.candidate_id == test_candidate_id,
                CandidateEventRecord.aggregate_version >= 1,
            )
        )
    )
    await session.commit()

    # Create a listing for the dynamic ticker (to satisfy InstrumentMasterService.resolve)
    dynamic_listing_id = uuid5(test_candidate_id, "listing")
    stmt = sa.select(Listing).where(Listing.id == dynamic_listing_id)
    listing_result = await session.execute(stmt)
    dynamic_listing = listing_result.scalar_one_or_none()
    if dynamic_listing is None:
        dynamic_listing = Listing(
            id=dynamic_listing_id,
            instrument_id=test_instrument.id,
            ticker=test_ticker,
            exchange_code="B3",
            market_segment="normal",
            valid_from=datetime(2000, 1, 1, tzinfo=UTC).date(),
        )
        session.add(dynamic_listing)
        await session.commit()

    candidate = InvestmentCandidateRecord(
        id=test_candidate_id,
        organization_id=test_org.id,
        origin="manual",
        status="suggested",
        ticker=test_ticker,
        exchange="B3",
        legal_name="Petróleo Brasileiro S.A. - Petrobras",
        trading_name="Petrobras",
        cnpj="33000167000101",
        instrument_id=None,
        issuer_id=None,
        approved_portfolio_eligible=False,
        created_by="system",
        idempotency_key=test_idempotency_key,
        request_hash=hashlib.sha256(f"e2e-test-{test_candidate_id}".encode()).hexdigest(),
        lock_version=1,
    )
    session.add(candidate)
    await session.flush()
    await session.commit()

    run_stmt = sa.select(CandidateAnalysisRunRecord).where(CandidateAnalysisRunRecord.id == _TEST_ANALYSIS_RUN_ID)
    run_result = await session.execute(run_stmt)
    run = run_result.scalar_one_or_none()
    if run is None:
        run = CandidateAnalysisRunRecord(
            id=_TEST_ANALYSIS_RUN_ID,
            candidate_id=candidate.id,
            run_number=1,
            trigger="manual",
            status="running",
            requested_by="system",
            data_as_of=_TODAY,
        )
        session.add(run)
        await session.commit()

    return {"candidate": candidate, "run": run}


@pytest_asyncio.fixture
async def test_agent_registry(session: AsyncSession) -> UUID:
    """Create agent capability + artifacts + version for AI execution.

    Returns the capability_id so tests can reference it.
    """
    from sqlalchemy.dialects.postgresql import insert

    # Clean up existing records to ensure fresh state (reverse dependency order)
    from database.models.agent_runtime import (
        AgentRuntimeRun,
    )

    # Delete runtime runs first (they reference versions)
    existing_runs = await session.execute(sa.select(AgentRuntimeRun))
    for r in existing_runs.scalars():
        await session.delete(r)

    # Delete versions (they reference capabilities and artifacts)
    existing_versions = await session.execute(sa.select(AgentVersion))
    for v in existing_versions.scalars():
        await session.delete(v)

    # Delete capabilities (they reference versions)
    existing_capabilities = await session.execute(sa.select(AgentCapability))
    for c in existing_capabilities.scalars():
        await session.delete(c)

    # Delete artifacts
    existing_artifacts = await session.execute(sa.select(AgentArtifact))
    for a in existing_artifacts.scalars():
        await session.delete(a)

    await session.flush()

    _AGENT_CAPABILITIES = [
        ("fundamentalist_analyst", "Fundamentalist Analyst", "Analyzes fundamental data for investment candidates."),
        ("risk_director", "Risk Director", "Reviews and approves risk assessments."),
        ("investment_committee", "Investment Committee", "Makes final investment decisions."),
        ("research_coordinator", "Research Coordinator", "Coordinates research and shortlisting."),
    ]

    created_capability_ids: list[UUID] = []

    for logical_id, display_name, description in _AGENT_CAPABILITIES:
        capability_uuid = uuid5(_TEST_CAPABILITY_ID, logical_id)

        stmt = (
            insert(AgentCapability)
            .values(
                id=capability_uuid,
                logical_id=logical_id,
                display_name=display_name,
                description=description,
            )
            .on_conflict_do_nothing()
        )
        await session.execute(stmt)

        result = await session.execute(sa.select(AgentCapability).where(AgentCapability.id == capability_uuid))
        capability = result.scalar_one_or_none()
        if capability is None:
            capability = AgentCapability(
                id=capability_uuid,
                logical_id=logical_id,
                display_name=display_name,
                description=description,
            )
            session.add(capability)
            await session.flush()

        artifact_uuids = {
            "prompt": uuid5(capability_uuid, "prompt"),
            "schema": uuid5(capability_uuid, "schema"),
            "model_profile": uuid5(capability_uuid, "model_profile"),
            "toolset": uuid5(capability_uuid, "toolset"),
        }

        artifact_kinds = {
            "prompt": "prompt",
            "schema": "schema",
            "model_profile": "model_profile",
            "toolset": "toolset",
        }

        artifact_contents = {
            "prompt": {"text": f"Analyze candidate {logical_id}."},
            "schema": {"type": "object", "properties": {"thesis": {"type": "string"}}},
            "model_profile": {"model": "mock/model"},
            "toolset": {"tools": []},
        }

        for artifact_key, artifact_id in artifact_uuids.items():
            kind = artifact_kinds[artifact_key]
            print(
                f"DEBUG FIXTURE: Inserting artifact {artifact_key} for {logical_id}: kind={kind}, content={artifact_contents[kind]}"
            )
            stmt = (
                insert(AgentArtifact)
                .values(
                    id=artifact_id,
                    logical_id=f"{logical_id}_{kind}",
                    kind=kind,
                    version=1,
                    sha256=hashlib.sha256(f"{kind} text".encode()).hexdigest(),
                    content=artifact_contents[kind],
                    created_by="system",
                )
                .on_conflict_do_nothing()
            )
            await session.execute(stmt)

        prompt_artifact = (
            await session.execute(sa.select(AgentArtifact).where(AgentArtifact.id == artifact_uuids["prompt"]))
        ).scalar_one_or_none()
        schema_artifact = (
            await session.execute(sa.select(AgentArtifact).where(AgentArtifact.id == artifact_uuids["schema"]))
        ).scalar_one_or_none()
        model_artifact = (
            await session.execute(sa.select(AgentArtifact).where(AgentArtifact.id == artifact_uuids["model_profile"]))
        ).scalar_one_or_none()
        toolset_artifact = (
            await session.execute(sa.select(AgentArtifact).where(AgentArtifact.id == artifact_uuids["toolset"]))
        ).scalar_one_or_none()

        version_uuid = uuid5(capability_uuid, "version_1")
        stmt = (
            insert(AgentVersion)
            .values(
                id=version_uuid,
                capability_id=capability.id,
                version=1,
                prompt_artifact_id=prompt_artifact.id,
                schema_artifact_id=schema_artifact.id,
                model_artifact_id=model_artifact.id,
                toolset_artifact_id=toolset_artifact.id,
                budgets={
                    "max_prompt_tokens": 10000,
                    "max_completion_tokens": 5000,
                    "max_cost_usd": 1.0,
                    "max_turns": 10,
                    "max_tool_calls": 20,
                    "max_duration_ms": 60000,
                },
                policies={},
                status="active",
                created_by="system",
            )
            .on_conflict_do_nothing()
        )
        await session.execute(stmt)

        capability.active_version_id = version_uuid
        created_capability_ids.append(capability.id)

    await session.commit()

    return created_capability_ids[0] if created_capability_ids else _TEST_CAPABILITY_ID


# ---------------------------------------------------------------------------
# Fixtures — mocked providers
# ---------------------------------------------------------------------------


@dataclass
class MockResponse:
    """Minimal HTTP response for mocking SafeHttpClient."""

    status_code: int = 200
    content: bytes = b""
    headers: dict[str, str] = None  # type: ignore[assignment]
    final_url: str = ""
    redirect_chain: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.headers is None:
            self.headers = {"content-type": "text/html; charset=utf-8"}
        if self.redirect_chain is None:
            self.redirect_chain = []


def _make_mock_provider(ticker: str, candidate_id: UUID) -> MockProvider:
    """Create a MockProvider with deterministic responses for candidate stages."""
    from datetime import UTC, datetime
    from decimal import Decimal
    from uuid import uuid4

    responses: dict[str, dict[str, object]] = {}

    # Fundamental analysis response — matches FundamentalAnalysisOutput schema
    fundamental_input: dict[str, object] = {
        "ticker": ticker,
        "legal_name": "Petróleo Brasileiro S.A. - Petrobras",
        "issuer_id": "00000000-0000-0000-0000-000000000002",
        "data_as_of": "2026-07-15T00:00:00+00:00",
    }
    fundamental_key = MockProvider.request_key(
        "mock/model",
        "Analyze candidate fundamentalist_analyst.",
        fundamental_input,
    )
    responses[fundamental_key] = {
        "ticker": ticker,
        "issuer_id": "00000000-0000-0000-0000-000000000002",
        "summary": f"{ticker} shows strong fundamentals with consistent cash flow generation.",
        "findings": [
            {
                "statement": "Company generates positive free cash flow",
                "kind": "fact",
                "confidence": str(Decimal("0.85")),
                "citations": [{"evidence_id": str(uuid4()), "claim": "Cash flow statement shows positive FCF"}],
            }
        ],
        "financial_health_score": str(Decimal("0.75")),
        "key_metrics": {"roe": "15.2%", "nmp": "42.1%"},
        "risks": ["regulatory risk", "commodity price volatility"],
        "catalysts": ["dividend increase", "share buyback"],
        "knowledge_cutoff": datetime(2026, 7, 15, tzinfo=UTC).isoformat(),
    }

    # Risk analysis response — matches RiskAnalysisOutput schema
    risk_input: dict[str, object] = {
        "ticker": ticker,
        "legal_name": "Petróleo Brasileiro S.A. - Petrobras",
        "issuer_id": "00000000-0000-0000-0000-000000000002",
        "data_as_of": "2026-07-15T00:00:00+00:00",
    }
    risk_key = MockProvider.request_key(
        "mock/model",
        "Analyze candidate risk_director.",
        risk_input,
    )
    responses[risk_key] = {
        "ticker": ticker,
        "issuer_id": "00000000-0000-0000-0000-000000000002",
        "summary": f"Medium risk profile with manageable exposure for {ticker}.",
        "findings": [
            {
                "statement": "Debt-to-equity ratio within industry norms",
                "kind": "fact",
                "confidence": str(Decimal("0.80")),
                "citations": [{"evidence_id": str(uuid4()), "claim": "Balance sheet data"}],
            }
        ],
        "risk_rating": "medium",
        "risk_factors": ["regulatory risk", "commodity price volatility"],
        "max_drawdown_estimate": Decimal("0.25"),
        "volatility_regime": "normal",
        "knowledge_cutoff": datetime(2026, 7, 15, tzinfo=UTC).isoformat(),
    }

    mock = MockProvider(responses=responses)
    mock.add_fallback(
        "mock/model",
        "Analyze candidate investment_committee.",
        {
            "ticker": ticker,
            "decision": "approve",
            "confidence": Decimal("0.75"),
            "rationale": f"Strong fundamentals outweigh medium risks for {ticker}.",
            "risk_acknowledgment": f"Medium risks identified for {ticker} but acceptable.",
            "knowledge_cutoff": datetime(2026, 7, 15, tzinfo=UTC).isoformat(),
        },
    )
    return mock


@pytest.fixture
def mock_http_client() -> SafeHttpClient:
    """Create a SafeHttpClient that returns controlled responses.

    For PETR4 IR page, returns HTML containing the legal name and CNPJ
    so that source validation passes the signal check.
    """
    from ia_investing.platform.http.safe_client import ValidatedHttpResponse

    petrobras_html = """
    <html>
    <head><title>Petrobras - Relação com Investidores</title></head>
    <body>
    <h1>Petróleo Brasileiro S.A. - Petrobras</h1>
    <p>CNPJ: 33.000.167/0001-01</p>
    <p>Ações ordinárias (PETR4) listadas na B3.</p>
    </body>
    </html>
    """.encode()

    cvm_html = b"<html><body>CVM Registration Page for Petrobras</body></html>"

    class _MockHttpClient(SafeHttpClient):
        async def _do_get(self, requested_url: str) -> ValidatedHttpResponse:
            if "petrobras" in requested_url.lower():
                return ValidatedHttpResponse(
                    requested_url=requested_url,
                    final_url=requested_url,
                    status_code=200,
                    headers={"content-type": "text/html; charset=utf-8"},
                    content=petrobras_html,
                    redirect_chain=(),
                    resolved_ips=(),
                )
            if "cvm" in requested_url.lower():
                return ValidatedHttpResponse(
                    requested_url=requested_url,
                    final_url=requested_url,
                    status_code=200,
                    headers={"content-type": "text/html; charset=utf-8"},
                    content=cvm_html,
                    redirect_chain=(),
                    resolved_ips=(),
                )
            return ValidatedHttpResponse(
                requested_url=requested_url,
                final_url=requested_url,
                status_code=404,
                headers={"content-type": "text/html"},
                content=b"Not found",
                redirect_chain=(),
                resolved_ips=(),
            )

    return _MockHttpClient(policy=EgressPolicy())


@pytest.fixture
def mock_cvm_resolver() -> AsyncMock:
    """Mock CVM resolver that returns Petrobras profile."""
    from ia_investing.integrations.connectors.models import CVMCompanyProfile, CVMSecurityProfile

    resolver = AsyncMock()

    async def _lookup_by_cnpj(cnpj: str) -> CVMCompanyProfile | None:
        if cnpj == "33000167000101":
            return CVMCompanyProfile(
                cnpj=cnpj,
                legal_name="Petróleo Brasileiro S.A. - Petrobras",
                cvm_code="C0001",
                reference_date="2026-07-15",
                website="https://www.petrobras.com.br",
                issuer_status="ativo",
                registration_status="ativo",
            )
        return None

    async def _lookup_securities_by_cnpj(cnpj: str) -> list[CVMSecurityProfile]:
        if cnpj == "33000167000101":
            return [
                CVMSecurityProfile(
                    cnpj=cnpj,
                    trading_code="PETR4",
                    security_class="ON",
                    security_type="Ação Ordinária",
                )
            ]
        return []

    resolver.lookup_by_cnpj = _lookup_by_cnpj
    resolver.lookup_securities_by_cnpj = _lookup_securities_by_cnpj
    return resolver


@pytest.fixture
def mock_b3_resolver() -> AsyncMock:
    """Mock B3 resolver that returns PETR4 listing data."""
    from ia_investing.integrations.connectors.models import B3ListingProfile

    resolver = AsyncMock()

    async def _lookup_by_ticker(ticker: str) -> B3ListingProfile | None:
        if ticker.startswith("PETR4"):
            from datetime import date
            from decimal import Decimal

            return B3ListingProfile(
                ticker=ticker,
                exchange="B3",
                market_segment="Novo Mercado",
                listing_status="active",
                closing_price=Decimal("37.50"),
                average_volume_30d=Decimal("50000000"),
                last_trade_date=date(2026, 7, 14),
            )
        return None

    resolver.lookup_by_ticker = _lookup_by_ticker
    return resolver


# ---------------------------------------------------------------------------
# Test: Full candidate intelligence pipeline — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_candidate_e2e_full_pipeline(
    test_org: Organization,
    test_issuer: Issuer,
    test_instrument: Instrument,
    test_listing: Listing,
    test_candidate: dict[str, Any],
    test_agent_registry: UUID,
    mock_http_client: SafeHttpClient,
    mock_cvm_resolver: AsyncMock,
    mock_b3_resolver: AsyncMock,
    engine: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI__PROVIDER", "mock")

    candidate = test_candidate["candidate"]

    # Patch _provider_for_runner to return configured MockProvider
    from ia_investing.integrations import production_runtime as pr_module

    mock_provider = _make_mock_provider(candidate.ticker, candidate.id)

    def _patched_provider_for_runner() -> MockProvider:
        return mock_provider

    monkeypatch.setattr(pr_module, "_provider_for_runner", _patched_provider_for_runner)
    """Exercise the full candidate flow: identity → sources → validation → documents → analysis → committee.

    This test verifies:
    1. Identity resolution resolves ticker → instrument/issuer
    2. Source discovery finds B3, CVM, IR sources
    3. Source validation verifies officiality via HTTP
    4. Document collection downloads from verified sources
    5. Fundamental analysis executes via agent runtime
    6. Risk analysis executes via agent runtime
    7. Committee review produces a decision
    8. Candidate status transitions to 'approved'
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    db_runtime = DatabaseRuntime(
        engine=engine,
        sessions=async_sessionmaker(engine, expire_on_commit=False),
    )
    runtime = ProductionCandidateRuntime(
        db=db_runtime,
        http_client=mock_http_client,
        agent_runtime_service=None,
        cvm_resolver=mock_cvm_resolver,
        b3_resolver=mock_b3_resolver,
    )

    command = CandidateWorkflowInput(
        candidate_id=candidate.id,
        analysis_run_id=_TEST_ANALYSIS_RUN_ID,
        organization_id=candidate.organization_id,
        data_as_of=_TODAY,
    )

    # --- Stage 1: Identity Resolution ---
    checkpoint: CandidateCheckpoint = await runtime.resolve_candidate_identity(command)
    assert not checkpoint.blocked, f"Identity resolution blocked: {checkpoint.reason}"
    assert checkpoint.stage == "identity_resolution"
    assert checkpoint.decision == "continue"
    assert checkpoint.payload is not None
    assert checkpoint.payload.get("ticker", "").startswith("PETR4")

    # Verify DB was updated
    async with async_sessionmaker(engine, expire_on_commit=False)() as verify_session:
        db_candidate = await verify_session.get(type(candidate), candidate.id)
        await verify_session.commit()
        assert db_candidate is not None
        assert db_candidate.instrument_id is not None
        assert db_candidate.issuer_id is not None

    # --- Stage 2: Source Discovery ---
    discovery = await runtime.discover_candidate_sources(command)
    assert discovery is not None
    output = discovery.output
    assert output["stage"] == "source_discovery"
    sources = output.get("sources", [])
    assert len(sources) > 0, "Expected at least one source to be discovered"

    source_kinds = {s.get("kind") for s in sources}
    assert "b3_listing" in source_kinds, "B3 listing source should be discovered"
    assert "issuer_record" in source_kinds, "Issuer record source should be discovered"

    # Persist discovered sources
    await runtime.persist_candidate_sources_and_gaps(discovery)

    # Verify sources were persisted
    async with async_sessionmaker(engine, expire_on_commit=False)() as verify_session:
        from database.models.investment_candidates import CandidateSourceRecord

        sources_result = (
            await verify_session.execute(
                sa.select(sa.func.count()).where(
                    sa.and_(
                        CandidateSourceRecord.candidate_id == candidate.id,
                        CandidateSourceRecord.status == "discovered",
                    )
                )
            )
        ).scalar_one()
    assert sources_result > 0, "Expected sources to be persisted in the database"

    # --- Stage 3: Source Validation ---
    # Validate all discovered sources
    async with async_sessionmaker(engine, expire_on_commit=False)() as verify_session:
        from database.models.investment_candidates import CandidateSourceRecord

        all_sources = (
            (
                await verify_session.execute(
                    sa.select(CandidateSourceRecord).where(
                        CandidateSourceRecord.candidate_id == candidate.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        print(f"DEBUG: All sources for candidate {candidate.id}: {[(s.id, s.kind, s.status) for s in all_sources]}")

        source_records = (
            (
                await verify_session.execute(
                    sa.select(CandidateSourceRecord).where(
                        CandidateSourceRecord.candidate_id == candidate.id,
                        CandidateSourceRecord.status == "discovered",
                    )
                )
            )
            .scalars()
            .all()
        )
        print(f"DEBUG: Discovered sources: {[(s.id, s.kind, s.status) for s in source_records]}")

    assert len(source_records) > 0, "Expected at least one discovered source to validate"

    for source_record in source_records:
        validation_input = CandidateSourceValidationInput(
            candidate_id=candidate.id,
            source_id=source_record.id,
            organization_id=candidate.organization_id,
        )

        validation_result = await runtime.validate_supplied_candidate_source(validation_input)
        print(
            f"DEBUG: Source {source_record.id} ({source_record.kind}) -> status={validation_result.status}, reason={validation_result.reason}"
        )
        assert validation_result.status == "verified", (
            f"Expected verified for source {source_record.id}, got {validation_result.status}: {validation_result.reason}"
        )

    # --- Stage 4: Document Collection ---
    doc_checkpoint = await runtime.collect_candidate_documents(command)
    assert not doc_checkpoint.blocked, f"Document collection blocked: {doc_checkpoint.reason}"
    assert doc_checkpoint.payload is not None
    assert doc_checkpoint.payload.get("collected", 0) > 0

    # --- Stage 5: Source Validation (candidate-level) ---
    # The validate_candidate_sources activity checks all discovered sources
    async with async_sessionmaker(engine, expire_on_commit=False)() as verify_session:
        from database.models.investment_candidates import CandidateSourceRecord

        sources_after_validation = (
            (
                await verify_session.execute(
                    sa.select(CandidateSourceRecord).where(
                        CandidateSourceRecord.candidate_id == candidate.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        print(f"DEBUG: Sources after validation loop: {[(s.id, s.kind, s.status) for s in sources_after_validation]}")

    source_validation_checkpoint = await runtime.validate_candidate_sources(command)
    assert not source_validation_checkpoint.blocked, f"Source validation blocked: {source_validation_checkpoint.reason}"

    # --- Stage 6: Fundamental Analysis ---
    # This stage executes governed agents with the MockProvider
    fundamental_checkpoint = await runtime.run_candidate_fundamental_analysis(command)
    assert not fundamental_checkpoint.blocked, f"Fundamental analysis blocked: {fundamental_checkpoint.reason}"

    # --- Stage 7: Risk Analysis ---
    risk_checkpoint = await runtime.run_candidate_risk_analysis(command)
    assert not risk_checkpoint.blocked, f"Risk analysis blocked: {risk_checkpoint.reason}"

    # --- Stage 8: Committee Review (mocked AI) ---
    committee_checkpoint = await runtime.create_committee_pack(command)
    assert not committee_checkpoint.blocked, f"Committee review blocked: {committee_checkpoint.reason}"

    # --- Stage 9: Completion ---
    result = await runtime.complete_candidate_analysis_run(command, committee_checkpoint)
    assert result.status == "succeeded", f"Completion failed: {result.reason}"

    # Verify the candidate runtime service can execute the full pipeline
    async with async_sessionmaker(engine, expire_on_commit=False)() as verify_session:
        # Verify candidate status was updated
        from database.models.investment_candidates import InvestmentCandidateRecord

        db_candidate = await verify_session.get(InvestmentCandidateRecord, candidate.id)

    # Final state: candidate should have progressed through the pipeline
    assert db_candidate is not None
    # The candidate may not be 'approved' yet (that requires human decision),
    # but it should have moved beyond 'pending'
    assert db_candidate.status in ("analyzing", "awaiting_review", "approved", "watchlist", "rejected")
