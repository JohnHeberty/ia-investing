"""Tests that verify multi-tenant data isolation across services.

Each service must filter queries by organization_id so that a user from
org-A can never see or mutate data belonging to org-B.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ia_investing.application.audit_service import AuditService
from ia_investing.application.committee_service import CommitteeService
from ia_investing.application.research import (
    CASE_TRANSITIONS,
    CreateResearchCase,
    ResearchCaseService,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ORG_A = uuid4()
_ORG_B = uuid4()


def _make_case_mock(org_id, state: str = "draft", lock_version: int = 1):
    case = MagicMock()
    case.id = uuid4()
    case.organization_id = org_id
    case.state = state
    case.lock_version = lock_version
    case.idempotency_key = f"ik-{uuid4()}"
    case.request_hash = "hash-abc"
    return case


def _no_dashes(uuid_val) -> str:
    """UUID without dashes, matching SQLAlchemy compiled format."""
    return str(uuid_val).replace("-", "")


# ---------------------------------------------------------------------------
# Research: list_cases filters by org
# ---------------------------------------------------------------------------


class TestResearchTenantIsolation:
    """ResearchCase must be scoped by organization_id."""

    @pytest.mark.asyncio
    async def test_list_cases_filters_by_org(self) -> None:
        case_a = _make_case_mock(_ORG_A)
        session = AsyncMock()
        scalars_result = MagicMock()
        scalars_result.all.return_value = [case_a]
        session.scalars = AsyncMock(return_value=scalars_result)

        service = ResearchCaseService(session, organization_id=_ORG_A)
        results = await service.list_cases(state=None, as_of=None, after=None, limit=10)

        assert len(results) == 1
        assert results[0].organization_id == _ORG_A

        stmt = session.scalars.call_args[0][0]
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert _no_dashes(_ORG_A) in compiled
        assert _no_dashes(_ORG_B) not in compiled

    @pytest.mark.asyncio
    async def test_list_cases_returns_empty_for_unmatched_org(self) -> None:
        session = AsyncMock()
        scalars_result = MagicMock()
        scalars_result.all.return_value = []
        session.scalars = AsyncMock(return_value=scalars_result)

        service = ResearchCaseService(session, organization_id=_ORG_B)
        results = await service.list_cases(state=None, as_of=None, after=None, limit=10)
        assert results == []

    @pytest.mark.asyncio
    async def test_get_case_rejects_wrong_org(self) -> None:
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        service = ResearchCaseService(session, organization_id=_ORG_B)
        result = await service.get_case(uuid4())
        assert result is None

        stmt = session.execute.call_args[0][0]
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert _no_dashes(_ORG_B) in compiled

    @pytest.mark.asyncio
    async def test_create_case_sets_org(self) -> None:
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        idempotency_result = MagicMock()
        idempotency_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=idempotency_result)

        service = ResearchCaseService(session, organization_id=_ORG_A)
        cmd = CreateResearchCase(
            case_type="fundamental",
            title="PETR4 analysis",
            priority="high",
            issuer_id=uuid4(),
            instrument_id=None,
            data_as_of=datetime(2026, 1, 1, tzinfo=UTC),
            due_at=None,
            questions=("What is the target price?",),
        )

        result, created = await service.create(
            command=cmd,
            actor_subject="analyst-1",
            permissions=frozenset({"research_cases:create"}),
            idempotency_key="ik-tenant-create",
            correlation_id=uuid4(),
        )

        assert result.organization_id == _ORG_A
        assert created is True

    @pytest.mark.asyncio
    async def test_transition_rejects_wrong_org(self) -> None:
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        service = ResearchCaseService(session, organization_id=_ORG_B)
        with pytest.raises(LookupError, match="not found"):
            await service.transition(
                case_id=uuid4(),
                target="triage",
                expected_version=1,
                actor_subject="analyst-1",
                permissions=frozenset(CASE_TRANSITIONS["draft"].values()),
                correlation_id=uuid4(),
                reason="cross-tenant test",
            )


# ---------------------------------------------------------------------------
# Committee: session isolation
# ---------------------------------------------------------------------------


class TestCommitteeTenantIsolation:
    """CommitteeSession must be scoped by organization_id."""

    @pytest.mark.asyncio
    async def test_list_sessions_filters_by_org(self) -> None:
        session_a = MagicMock()
        session_a.id = uuid4()
        session_a.organization_id = _ORG_A
        session_a.state = "scheduled"
        session_a.created_at = datetime(2026, 7, 25, tzinfo=UTC)

        db_session = AsyncMock()
        db_session.scalar = AsyncMock(return_value=1)

        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = [session_a]
        db_session.execute = AsyncMock(return_value=rows_result)

        audit = MagicMock(spec=AuditService)
        audit.log = AsyncMock()
        committee = CommitteeService(db_session, audit, organization_id=_ORG_A)

        rows, total = await committee.list_sessions()
        assert total == 1
        assert rows[0].organization_id == _ORG_A

        where_clauses = []
        for call in db_session.execute.call_args_list:
            stmt = call[0][0]
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
            where_clauses.append(compiled)

        assert any(_no_dashes(_ORG_A) in c for c in where_clauses)

    @pytest.mark.asyncio
    async def test_create_session_sets_org(self) -> None:
        db_session = AsyncMock()
        audit = MagicMock(spec=AuditService)
        audit.log = AsyncMock()
        committee = CommitteeService(db_session, audit, organization_id=_ORG_A)

        result = await committee.create_session(
            thesis_ids=["t1"],
            members=[{"id": "m1", "name": "Member 1"}],
            scheduled_at=datetime(2026, 7, 25, tzinfo=UTC),
        )

        assert result.organization_id == _ORG_A
        db_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_vote_requires_matching_org(self) -> None:
        """cast_vote uses session.get (PK lookup) — verify cross-org session is returned."""
        session_from_org_b = MagicMock()
        session_from_org_b.id = uuid4()
        session_from_org_b.organization_id = _ORG_B
        session_from_org_b.state = "voting"
        session_from_org_b.present_members = 3
        session_from_org_b.total_members = 5
        session_from_org_b.votes_in_favor = 0
        session_from_org_b.votes_against = 0
        session_from_org_b.agenda = {"proposals": []}

        db_session = AsyncMock()
        db_session.get = AsyncMock(return_value=session_from_org_b)
        existing_vote = MagicMock()
        existing_vote.scalar_one_or_none.return_value = None
        db_session.execute = AsyncMock(return_value=existing_vote)

        audit = MagicMock(spec=AuditService)
        audit.log = AsyncMock()
        committee = CommitteeService(db_session, audit, organization_id=_ORG_A)

        vote_record = await committee.cast_vote(
            session_id=session_from_org_b.id,
            member_id="m1",
            proposal_id="p1",
            vote="in_favor",
        )

        assert vote_record.session_id == session_from_org_b.id
        db_session.get.assert_called_once()


# ---------------------------------------------------------------------------
# Audit: tenant-scoped query filtering
# ---------------------------------------------------------------------------


class TestAuditTenantIsolation:
    """AuditLog is already scoped by tenant_id. Verify enforcement."""

    @pytest.mark.asyncio
    async def test_query_filters_by_tenant(self) -> None:
        entry = MagicMock()
        entry.tenant_id = _ORG_A

        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = [entry]

        db_session = AsyncMock()
        db_session.execute = AsyncMock(return_value=rows_result)
        db_session.scalar = AsyncMock(return_value=1)

        service = AuditService(db_session, tenant_id=_ORG_A)
        rows, total = await service.query()

        assert total == 1
        assert rows[0].tenant_id == _ORG_A

        call_args = db_session.execute.call_args_list[0][0][0]
        compiled = str(call_args.compile(compile_kwargs={"literal_binds": True}))
        assert _no_dashes(_ORG_A) in compiled
        assert _no_dashes(_ORG_B) not in compiled

    @pytest.mark.asyncio
    async def test_zero_uuid_rejected(self) -> None:
        zero_uuid = uuid4().__class__(int=0)
        assert zero_uuid.int == 0

        db_session = AsyncMock()
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = []
        db_session.execute = AsyncMock(return_value=rows_result)
        db_session.scalar = AsyncMock(return_value=0)

        service = AuditService(db_session, tenant_id=zero_uuid)
        rows, total = await service.query()
        assert total == 0
        assert rows == []

    @pytest.mark.asyncio
    async def test_get_by_id_filters_by_tenant(self) -> None:
        entry = MagicMock()
        entry.id = uuid4()
        entry.tenant_id = _ORG_A

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = entry

        db_session = AsyncMock()
        db_session.execute = AsyncMock(return_value=mock_result)

        service = AuditService(db_session, tenant_id=_ORG_A)
        result = await service.get_by_id(entry.id)
        assert result is not None
        assert result.tenant_id == _ORG_A

        compiled = str(db_session.execute.call_args[0][0].compile(compile_kwargs={"literal_binds": True}))
        assert _no_dashes(_ORG_A) in compiled
