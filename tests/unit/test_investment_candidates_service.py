from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from database.models.investment_candidates import (
    CandidateAnalysisRunRecord,
    CandidateEventRecord,
    CandidateGapRecord,
    CandidateSourceRecord,
    ExplorationRunRecord,
    ExplorationSuggestionRecord,
    InvestmentCandidateRecord,
)
from database.models.research import DomainOutboxEvent
from ia_investing.application.investment_candidates import (
    CandidateConcurrencyError,
    CandidateDuplicateError,
    CandidateIdempotencyConflictError,
    InvestmentCandidateApplicationService,
    _request_hash,
    _url_hash,
)
from ia_investing.candidate_intelligence.contracts import (
    CandidateCreateRequest,
    CandidateReanalysisRequest,
    CandidateSourceCreateRequest,
    CandidateSourceCreateRequest as SrcCreateReq,
    ExplorationCreateRequest,
)
from ia_investing.candidate_intelligence.enums import (
    AnalysisTrigger,
    CandidateStatus,
    SourceKind,
)

pytestmark = pytest.mark.unit

ORG_ID = uuid4()
ACTOR = "user@test.com"
NOW = datetime(2026, 7, 27, 12, 0, 0, tzinfo=UTC)
PERMS_CREATE = frozenset({"candidates:create"})
PERMS_READ = frozenset({"candidates:read"})
PERMS_UPDATE = frozenset({"candidates:update"})
PERMS_REANALYZE = frozenset({"candidates:reanalyze"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candidate(
    *,
    id: UUID | None = None,
    status: str = CandidateStatus.IDENTITY_RESOLUTION.value,
    lock_version: int = 1,
    idempotency_key: str = "key-1",
    request_hash: str | None = None,
    exchange: str = "B3",
    ticker: str = "PETR4",
) -> InvestmentCandidateRecord:
    c = MagicMock(spec=InvestmentCandidateRecord)
    c.id = id or uuid4()
    c.organization_id = ORG_ID
    c.status = status
    c.lock_version = lock_version
    c.idempotency_key = idempotency_key
    c.request_hash = request_hash or _request_hash({"ticker": ticker, "exchange": exchange})
    c.exchange = exchange
    c.ticker = ticker
    c.updated_at = NOW
    return c


def _make_run(candidate_id: UUID, run_number: int = 1) -> CandidateAnalysisRunRecord:
    r = MagicMock(spec=CandidateAnalysisRunRecord)
    r.id = uuid4()
    r.candidate_id = candidate_id
    r.run_number = run_number
    r.status = "queued"
    return r


def _make_gap(
    *,
    id: UUID | None = None,
    candidate_id: UUID | None = None,
    status: str = "open",
    level: str = "blocking",
    source_kind: str | None = "investor_relations",
    code: str = "investor_relations",
) -> CandidateGapRecord:
    g = MagicMock(spec=CandidateGapRecord)
    g.id = id or uuid4()
    g.candidate_id = candidate_id or uuid4()
    g.status = status
    g.level = level
    g.source_kind = source_kind
    g.code = code
    g.resolved_at = None
    g.resolved_by = None
    g.resolution_notes = None
    return g


def _make_suggestion(
    *,
    id: UUID | None = None,
    status: str = "new",
    expires_at: datetime | None = None,
    promoted_candidate_id: UUID | None = None,
    ticker: str = "VALE3",
    exchange: str = "B3",
    source_snapshot: list[dict[str, Any]] | None = None,
) -> ExplorationSuggestionRecord:
    s = MagicMock(spec=ExplorationSuggestionRecord)
    s.id = id or uuid4()
    s.status = status
    s.expires_at = expires_at
    s.promoted_candidate_id = promoted_candidate_id
    s.ticker = ticker
    s.exchange = exchange
    s.source_snapshot = source_snapshot or []
    s.instrument_id = uuid4()
    s.issuer_id = uuid4()
    s.rationale = "test"
    return s


def _session_mock() -> MagicMock:
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    session.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# _require permission checks
# ---------------------------------------------------------------------------

class TestRequirePermissions:
    def test_granted_passes(self) -> None:
        InvestmentCandidateApplicationService._require(PERMS_CREATE, "candidates:create")

    def test_any_of_multiple_passes(self) -> None:
        InvestmentCandidateApplicationService._require(PERMS_READ, "candidates:read", "research:read")

    def test_missing_raises(self) -> None:
        with pytest.raises(PermissionError, match="permission required"):
            InvestmentCandidateApplicationService._require(frozenset(), "candidates:create")


# ---------------------------------------------------------------------------
# create_manual
# ---------------------------------------------------------------------------

class TestCreateManual:
    @pytest.fixture()
    def svc(self, _session_mock: Any = None) -> tuple[InvestmentCandidateApplicationService, MagicMock]:
        session = _session_mock or AsyncMock()
        return InvestmentCandidateApplicationService(session), session

    def _request(self) -> CandidateCreateRequest:
        return CandidateCreateRequest(ticker="petr4", exchange="B3", rationale="test")

    @pytest.mark.asyncio
    async def test_happy_path_creates_candidate(self) -> None:
        session = AsyncMock()
        session.scalar = AsyncMock(return_value=None)  # no existing, no duplicate
        session.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        svc = InvestmentCandidateApplicationService(session)

        candidate, run, is_new = await svc.create_manual(
            organization_id=ORG_ID,
            actor_id=ACTOR,
            permissions=PERMS_CREATE,
            request=self._request(),
            data_as_of=NOW,
            idempotency_key="key-1",
            correlation_id=uuid4(),
        )
        assert is_new is True
        assert session.add.called
        assert session.commit.called

    @pytest.mark.asyncio
    async def test_idempotency_returns_existing_when_same_hash(self) -> None:
        from ia_investing.application.investment_candidates import utcnow as _utcnow

        req = self._request()
        now = datetime(2026, 7, 27, 12, 0, 0, tzinfo=UTC)
        payload = req.model_dump(mode="json") | {"data_as_of": now.isoformat()}
        correct_hash = _request_hash(payload)

        session = AsyncMock()
        candidate = _make_candidate(idempotency_key="key-1", request_hash=correct_hash)
        first_run = _make_run(candidate.id)
        session.scalar = AsyncMock(side_effect=[candidate, first_run])
        svc = InvestmentCandidateApplicationService(session)

        result_candidate, result_run, is_new = await svc.create_manual(
            organization_id=ORG_ID,
            actor_id=ACTOR,
            permissions=PERMS_CREATE,
            request=req,
            data_as_of=now,
            idempotency_key="key-1",
            correlation_id=uuid4(),
        )
        assert is_new is False
        assert result_candidate is candidate
        assert result_run is first_run

    @pytest.mark.asyncio
    async def test_idempotency_conflict_on_different_hash(self) -> None:
        session = AsyncMock()
        candidate = _make_candidate(idempotency_key="key-1", request_hash="old_hash")
        session.scalar = AsyncMock(return_value=candidate)
        svc = InvestmentCandidateApplicationService(session)

        with pytest.raises(CandidateIdempotencyConflictError, match="different candidate request"):
            await svc.create_manual(
                organization_id=ORG_ID,
                actor_id=ACTOR,
                permissions=PERMS_CREATE,
                request=self._request(),
                data_as_of=NOW,
                idempotency_key="key-1",
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_duplicate_ticker_raises(self) -> None:
        session = AsyncMock()
        dup = _make_candidate(ticker="PETR4", exchange="B3")
        # First scalar: no idempotency match; Second scalar: duplicate found
        session.scalar = AsyncMock(side_effect=[None, dup])
        svc = InvestmentCandidateApplicationService(session)

        with pytest.raises(CandidateDuplicateError, match="active candidate already exists"):
            await svc.create_manual(
                organization_id=ORG_ID,
                actor_id=ACTOR,
                permissions=PERMS_CREATE,
                request=self._request(),
                data_as_of=NOW,
                idempotency_key="new-key",
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_permission_denied(self) -> None:
        session = AsyncMock()
        svc = InvestmentCandidateApplicationService(session)
        with pytest.raises(PermissionError):
            await svc.create_manual(
                organization_id=ORG_ID,
                actor_id=ACTOR,
                permissions=frozenset(),
                request=self._request(),
                data_as_of=NOW,
                idempotency_key="key-1",
                correlation_id=uuid4(),
            )


# ---------------------------------------------------------------------------
# add_source
# ---------------------------------------------------------------------------

class TestAddSource:
    @pytest.mark.asyncio
    async def test_happy_path_adds_source(self) -> None:
        session = AsyncMock()
        candidate = _make_candidate()
        session.scalar = AsyncMock(side_effect=[candidate, None])  # locked candidate, no existing source
        svc = InvestmentCandidateApplicationService(session)

        req = CandidateSourceCreateRequest(
            kind=SourceKind.INVESTOR_RELATIONS,
            url="https://ir.example.com",
        )
        result = await svc.add_source(
            candidate_id=candidate.id,
            organization_id=ORG_ID,
            actor_id=ACTOR,
            permissions=PERMS_UPDATE,
            request=req,
            expected_version=1,
            correlation_id=uuid4(),
        )
        assert session.add.called
        assert session.commit.called

    @pytest.mark.asyncio
    async def test_duplicate_source_returns_existing(self) -> None:
        session = AsyncMock()
        candidate = _make_candidate()
        existing_src = MagicMock(spec=CandidateSourceRecord)
        session.scalar = AsyncMock(side_effect=[candidate, existing_src])
        svc = InvestmentCandidateApplicationService(session)

        req = CandidateSourceCreateRequest(
            kind=SourceKind.INVESTOR_RELATIONS,
            url="https://ir.example.com",
        )
        result = await svc.add_source(
            candidate_id=candidate.id,
            organization_id=ORG_ID,
            actor_id=ACTOR,
            permissions=PERMS_UPDATE,
            request=req,
            expected_version=1,
            correlation_id=uuid4(),
        )
        assert result is existing_src

    @pytest.mark.asyncio
    async def test_cancelled_candidate_rejects_source(self) -> None:
        session = AsyncMock()
        candidate = _make_candidate(status=CandidateStatus.CANCELLED.value)
        session.scalar = AsyncMock(return_value=candidate)
        svc = InvestmentCandidateApplicationService(session)

        req = CandidateSourceCreateRequest(
            kind=SourceKind.INVESTOR_RELATIONS,
            url="https://ir.example.com",
        )
        with pytest.raises(ValueError, match="cancelled candidates cannot receive"):
            await svc.add_source(
                candidate_id=candidate.id,
                organization_id=ORG_ID,
                actor_id=ACTOR,
                permissions=PERMS_UPDATE,
                request=req,
                expected_version=1,
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_candidate_not_found(self) -> None:
        session = AsyncMock()
        session.scalar = AsyncMock(return_value=None)
        svc = InvestmentCandidateApplicationService(session)

        req = CandidateSourceCreateRequest(
            kind=SourceKind.INVESTOR_RELATIONS,
            url="https://ir.example.com",
        )
        with pytest.raises(LookupError, match="investment candidate not found"):
            await svc.add_source(
                candidate_id=uuid4(),
                organization_id=ORG_ID,
                actor_id=ACTOR,
                permissions=PERMS_UPDATE,
                request=req,
                expected_version=1,
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_version_mismatch_raises(self) -> None:
        session = AsyncMock()
        candidate = _make_candidate(lock_version=2)
        session.scalar = AsyncMock(return_value=candidate)
        svc = InvestmentCandidateApplicationService(session)

        req = CandidateSourceCreateRequest(
            kind=SourceKind.INVESTOR_RELATIONS,
            url="https://ir.example.com",
        )
        with pytest.raises(CandidateConcurrencyError, match="expected candidate version"):
            await svc.add_source(
                candidate_id=candidate.id,
                organization_id=ORG_ID,
                actor_id=ACTOR,
                permissions=PERMS_UPDATE,
                request=req,
                expected_version=5,
                correlation_id=uuid4(),
            )


# ---------------------------------------------------------------------------
# resolve_gap
# ---------------------------------------------------------------------------

class TestResolveGap:
    @pytest.mark.asyncio
    async def test_happy_path_resolves_gap(self) -> None:
        session = AsyncMock()
        candidate = _make_candidate()
        gap = _make_gap(candidate_id=candidate.id, level="required")
        session.scalar = AsyncMock(side_effect=[candidate, gap])
        svc = InvestmentCandidateApplicationService(session)

        result = await svc.resolve_gap(
            candidate_id=candidate.id,
            gap_id=gap.id,
            organization_id=ORG_ID,
            actor_id=ACTOR,
            permissions=PERMS_UPDATE,
            notes="User provided URL",
            expected_version=1,
        )
        assert result.status == "resolved"
        assert session.commit.called

    @pytest.mark.asyncio
    async def test_gap_not_found(self) -> None:
        session = AsyncMock()
        candidate = _make_candidate()
        session.scalar = AsyncMock(side_effect=[candidate, None])
        svc = InvestmentCandidateApplicationService(session)

        with pytest.raises(LookupError, match="candidate gap not found"):
            await svc.resolve_gap(
                candidate_id=candidate.id,
                gap_id=uuid4(),
                organization_id=ORG_ID,
                actor_id=ACTOR,
                permissions=PERMS_UPDATE,
                notes="resolved",
                expected_version=1,
            )

    @pytest.mark.asyncio
    async def test_already_resolved_gap_raises(self) -> None:
        session = AsyncMock()
        candidate = _make_candidate()
        gap = _make_gap(candidate_id=candidate.id, status="resolved")
        session.scalar = AsyncMock(side_effect=[candidate, gap])
        svc = InvestmentCandidateApplicationService(session)

        with pytest.raises(ValueError, match="only open gaps can be resolved"):
            await svc.resolve_gap(
                candidate_id=candidate.id,
                gap_id=gap.id,
                organization_id=ORG_ID,
                actor_id=ACTOR,
                permissions=PERMS_UPDATE,
                notes="too late",
                expected_version=1,
            )

    @pytest.mark.asyncio
    async def test_blocking_gap_without_verified_source_raises(self) -> None:
        session = AsyncMock()
        candidate = _make_candidate()
        gap = _make_gap(candidate_id=candidate.id, level="blocking", source_kind="investor_relations")
        # scalar: candidate, gap, then count=0 (no verified sources)
        session.scalar = AsyncMock(side_effect=[candidate, gap, 0])
        svc = InvestmentCandidateApplicationService(session)

        with pytest.raises(ValueError, match="blocking source gap can only be resolved"):
            await svc.resolve_gap(
                candidate_id=candidate.id,
                gap_id=gap.id,
                organization_id=ORG_ID,
                actor_id=ACTOR,
                permissions=PERMS_UPDATE,
                notes="user provided url",
                expected_version=1,
            )

    @pytest.mark.asyncio
    async def test_blocking_gap_with_verified_source_succeeds(self) -> None:
        session = AsyncMock()
        candidate = _make_candidate()
        gap = _make_gap(candidate_id=candidate.id, level="blocking", source_kind="investor_relations")
        # scalar: candidate, gap, count=1 (verified source exists)
        session.scalar = AsyncMock(side_effect=[candidate, gap, 1])
        svc = InvestmentCandidateApplicationService(session)

        result = await svc.resolve_gap(
            candidate_id=candidate.id,
            gap_id=gap.id,
            organization_id=ORG_ID,
            actor_id=ACTOR,
            permissions=PERMS_UPDATE,
            notes="verified",
            expected_version=1,
        )
        assert result.status == "resolved"


# ---------------------------------------------------------------------------
# request_reanalysis
# ---------------------------------------------------------------------------

class TestRequestReanalysis:
    def _req(self, allow_incomplete: bool = False) -> CandidateReanalysisRequest:
        return CandidateReanalysisRequest(
            trigger=AnalysisTrigger.MANUAL_RETRY,
            data_as_of=NOW,
            allow_incomplete=allow_incomplete,
        )

    @pytest.mark.asyncio
    async def test_happy_path_creates_run(self) -> None:
        session = AsyncMock()
        candidate = _make_candidate()
        # scalar: candidate, blockers (empty), max run_number
        session.scalar = AsyncMock(side_effect=[candidate, None])
        session.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        # coalesce max
        session.scalar = AsyncMock(side_effect=[candidate, None, 1])
        svc = InvestmentCandidateApplicationService(session)

        run = await svc.request_reanalysis(
            candidate_id=candidate.id,
            organization_id=ORG_ID,
            actor_id=ACTOR,
            permissions=PERMS_REANALYZE,
            request=self._req(),
            expected_version=1,
            correlation_id=uuid4(),
        )
        assert session.add.called
        assert session.commit.called

    @pytest.mark.asyncio
    async def test_blocking_gaps_without_allow_incomplete_raises(self) -> None:
        session = AsyncMock()
        candidate = _make_candidate()
        gap = _make_gap(code="investor_relations", level="blocking")
        session.scalar = AsyncMock(side_effect=[candidate, gap])
        session.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=["investor_relations"])))
        svc = InvestmentCandidateApplicationService(session)

        with pytest.raises(ValueError, match="candidate still has blocking gaps"):
            await svc.request_reanalysis(
                candidate_id=candidate.id,
                organization_id=ORG_ID,
                actor_id=ACTOR,
                permissions=PERMS_REANALYZE,
                request=self._req(allow_incomplete=False),
                expected_version=1,
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_blocking_gaps_with_allow_incomplete_succeeds(self) -> None:
        session = AsyncMock()
        candidate = _make_candidate()
        session.scalar = AsyncMock(side_effect=[candidate, None, 0])
        session.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=["investor_relations"])))
        svc = InvestmentCandidateApplicationService(session)

        run = await svc.request_reanalysis(
            candidate_id=candidate.id,
            organization_id=ORG_ID,
            actor_id=ACTOR,
            permissions=PERMS_REANALYZE,
            request=self._req(allow_incomplete=True),
            expected_version=1,
            correlation_id=uuid4(),
        )
        assert session.commit.called

    @pytest.mark.asyncio
    async def test_disallowed_status_raises(self) -> None:
        session = AsyncMock()
        candidate = _make_candidate(status=CandidateStatus.APPROVED.value)
        session.scalar = AsyncMock(return_value=candidate)
        svc = InvestmentCandidateApplicationService(session)

        with pytest.raises(ValueError, match="cannot restart onboarding"):
            await svc.request_reanalysis(
                candidate_id=candidate.id,
                organization_id=ORG_ID,
                actor_id=ACTOR,
                permissions=PERMS_REANALYZE,
                request=self._req(),
                expected_version=1,
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_permission_denied(self) -> None:
        session = AsyncMock()
        svc = InvestmentCandidateApplicationService(session)
        with pytest.raises(PermissionError):
            await svc.request_reanalysis(
                candidate_id=uuid4(),
                organization_id=ORG_ID,
                actor_id=ACTOR,
                permissions=frozenset(),
                request=self._req(),
                expected_version=1,
                correlation_id=uuid4(),
            )


# ---------------------------------------------------------------------------
# list_candidates
# ---------------------------------------------------------------------------

class TestListCandidates:
    @pytest.mark.asyncio
    async def test_basic_list(self) -> None:
        session = AsyncMock()
        c1, c2 = _make_candidate(), _make_candidate()
        session.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[c1, c2])))
        svc = InvestmentCandidateApplicationService(session)

        result = await svc.list_candidates(
            organization_id=ORG_ID,
            permissions=PERMS_READ,
            status=None,
            after=None,
            limit=50,
        )
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_permission_denied(self) -> None:
        session = AsyncMock()
        svc = InvestmentCandidateApplicationService(session)
        with pytest.raises(PermissionError):
            await svc.list_candidates(
                organization_id=ORG_ID,
                permissions=frozenset(),
                status=None,
                after=None,
                limit=50,
            )


# ---------------------------------------------------------------------------
# get_detail
# ---------------------------------------------------------------------------

class TestGetDetail:
    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        session = AsyncMock()
        session.scalar = AsyncMock(return_value=None)
        svc = InvestmentCandidateApplicationService(session)

        result = await svc.get_detail(
            candidate_id=uuid4(),
            organization_id=ORG_ID,
            permissions=PERMS_READ,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_detail_with_relations(self) -> None:
        session = AsyncMock()
        candidate = _make_candidate()
        session.scalar = AsyncMock(return_value=candidate)
        empty_result = MagicMock()
        empty_result.all = MagicMock(return_value=[])
        session.scalars = AsyncMock(return_value=empty_result)
        svc = InvestmentCandidateApplicationService(session)

        detail = await svc.get_detail(
            candidate_id=candidate.id,
            organization_id=ORG_ID,
            permissions=PERMS_READ,
        )
        assert detail is not None
        assert detail.candidate is candidate


# ---------------------------------------------------------------------------
# dismiss_suggestion
# ---------------------------------------------------------------------------

class TestDismissSuggestion:
    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        session = AsyncMock()
        s = _make_suggestion()
        session.scalar = AsyncMock(return_value=s)
        svc = InvestmentCandidateApplicationService(session)

        result = await svc.dismiss_suggestion(
            suggestion_id=s.id,
            organization_id=ORG_ID,
            actor_id=ACTOR,
            permissions=PERMS_UPDATE,
            reason="Not interested",
        )
        assert result.status == "dismissed"
        assert session.commit.called

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        session = AsyncMock()
        session.scalar = AsyncMock(return_value=None)
        svc = InvestmentCandidateApplicationService(session)

        with pytest.raises(LookupError, match="exploration suggestion not found"):
            await svc.dismiss_suggestion(
                suggestion_id=uuid4(),
                organization_id=ORG_ID,
                actor_id=ACTOR,
                permissions=PERMS_UPDATE,
                reason="nope",
            )

    @pytest.mark.asyncio
    async def test_already_dismissed_raises(self) -> None:
        session = AsyncMock()
        s = _make_suggestion(status="dismissed")
        session.scalar = AsyncMock(return_value=s)
        svc = InvestmentCandidateApplicationService(session)

        with pytest.raises(ValueError, match="only new suggestions can be dismissed"):
            await svc.dismiss_suggestion(
                suggestion_id=s.id,
                organization_id=ORG_ID,
                actor_id=ACTOR,
                permissions=PERMS_UPDATE,
                reason="again",
            )

    @pytest.mark.asyncio
    async def test_expired_suggestion_raises(self) -> None:
        session = AsyncMock()
        s = _make_suggestion(expires_at=datetime(2020, 1, 1, tzinfo=UTC))
        session.scalar = AsyncMock(return_value=s)
        svc = InvestmentCandidateApplicationService(session)

        with pytest.raises(ValueError, match="expired exploration suggestions cannot be dismissed"):
            await svc.dismiss_suggestion(
                suggestion_id=s.id,
                organization_id=ORG_ID,
                actor_id=ACTOR,
                permissions=PERMS_UPDATE,
                reason="expired",
            )


# ---------------------------------------------------------------------------
# promote_suggestion
# ---------------------------------------------------------------------------

class TestPromoteSuggestion:
    @pytest.mark.asyncio
    async def test_happy_path_creates_candidate(self) -> None:
        session = AsyncMock()
        s = _make_suggestion()
        # scalar: suggestion, no duplicate
        session.scalar = AsyncMock(side_effect=[s, None])
        session.flush = AsyncMock()
        svc = InvestmentCandidateApplicationService(session)

        result = await svc.promote_suggestion(
            suggestion_id=s.id,
            organization_id=ORG_ID,
            actor_id=ACTOR,
            permissions=PERMS_CREATE,
            idempotency_key="promo-1",
            correlation_id=uuid4(),
        )
        assert session.add.called
        assert session.commit.called

    @pytest.mark.asyncio
    async def test_already_promoted_returns_existing(self) -> None:
        session = AsyncMock()
        candidate = _make_candidate()
        s = _make_suggestion(status="promoted", promoted_candidate_id=candidate.id)
        session.scalar = AsyncMock(return_value=s)
        session.get = AsyncMock(return_value=candidate)
        svc = InvestmentCandidateApplicationService(session)

        result = await svc.promote_suggestion(
            suggestion_id=s.id,
            organization_id=ORG_ID,
            actor_id=ACTOR,
            permissions=PERMS_CREATE,
            idempotency_key="promo-1",
            correlation_id=uuid4(),
        )
        assert result is candidate

    @pytest.mark.asyncio
    async def test_duplicate_candidate_marks_duplicate(self) -> None:
        session = AsyncMock()
        s = _make_suggestion(ticker="VALE3", exchange="B3")
        dup = _make_candidate(ticker="VALE3", exchange="B3")
        # scalar: suggestion, duplicate candidate
        session.scalar = AsyncMock(side_effect=[s, dup])
        svc = InvestmentCandidateApplicationService(session)

        result = await svc.promote_suggestion(
            suggestion_id=s.id,
            organization_id=ORG_ID,
            actor_id=ACTOR,
            permissions=PERMS_CREATE,
            idempotency_key="promo-1",
            correlation_id=uuid4(),
        )
        assert result is dup

    @pytest.mark.asyncio
    async def test_expired_suggestion_raises(self) -> None:
        session = AsyncMock()
        s = _make_suggestion(expires_at=datetime(2020, 1, 1, tzinfo=UTC))
        session.scalar = AsyncMock(return_value=s)
        svc = InvestmentCandidateApplicationService(session)

        with pytest.raises(ValueError, match="expired exploration suggestions cannot be promoted"):
            await svc.promote_suggestion(
                suggestion_id=s.id,
                organization_id=ORG_ID,
                actor_id=ACTOR,
                permissions=PERMS_CREATE,
                idempotency_key="promo-1",
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        session = AsyncMock()
        session.scalar = AsyncMock(return_value=None)
        svc = InvestmentCandidateApplicationService(session)

        with pytest.raises(LookupError, match="exploration suggestion not found"):
            await svc.promote_suggestion(
                suggestion_id=uuid4(),
                organization_id=ORG_ID,
                actor_id=ACTOR,
                permissions=PERMS_CREATE,
                idempotency_key="promo-1",
                correlation_id=uuid4(),
            )


# ---------------------------------------------------------------------------
# Exploration CRUD
# ---------------------------------------------------------------------------

class TestExplorationRuns:
    @pytest.mark.asyncio
    async def test_create_exploration_run(self) -> None:
        session = AsyncMock()
        svc = InvestmentCandidateApplicationService(session)
        req = ExplorationCreateRequest(
            strategy_codes=("momentum",),
            data_as_of=NOW,
            minimum_liquidity=Decimal("1000000"),
        )
        run = await svc.create_exploration_run(
            organization_id=ORG_ID,
            actor_id=ACTOR,
            permissions=frozenset({"exploration:create"}),
            request=req,
            correlation_id=uuid4(),
        )
        assert session.add.called
        assert session.commit.called

    @pytest.mark.asyncio
    async def test_list_exploration_runs(self) -> None:
        session = AsyncMock()
        session.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        svc = InvestmentCandidateApplicationService(session)
        result = await svc.list_exploration_runs(
            organization_id=ORG_ID,
            permissions=frozenset({"exploration:read"}),
            status=None,
            limit=10,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_get_exploration_detail_not_found(self) -> None:
        session = AsyncMock()
        session.scalar = AsyncMock(return_value=None)
        svc = InvestmentCandidateApplicationService(session)
        result = await svc.get_exploration_detail(
            exploration_run_id=uuid4(),
            organization_id=ORG_ID,
            permissions=frozenset({"exploration:read"}),
        )
        assert result is None


# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------

class TestHashHelpers:
    def test_request_hash_deterministic(self) -> None:
        h1 = _request_hash({"a": 1, "b": 2})
        h2 = _request_hash({"a": 1, "b": 2})
        assert h1 == h2
        assert len(h1) == 64

    def test_request_hash_different_for_different_input(self) -> None:
        h1 = _request_hash({"a": 1})
        h2 = _request_hash({"a": 2})
        assert h1 != h2

    def test_url_hash_length(self) -> None:
        h = _url_hash("https://example.com")
        assert len(h) == 64
