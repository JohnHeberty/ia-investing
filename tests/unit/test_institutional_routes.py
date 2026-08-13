"""Tests for apps.api.routes.institutional — agent runs, operations, dashboard."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from apps.api.routes.institutional import (
    AgentRunAccepted,
    AgentRunRequest,
    OperationStatusResponse,
    _mark_dispatched,
    get_operation_status,
    organization_uuid,
    start_agent_run,
)

# ---------------------------------------------------------------------------
# AgentRunRequest model validation
# ---------------------------------------------------------------------------


class TestAgentRunRequest:
    def test_valid_request(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        req = AgentRunRequest(
            capability="research",
            input_payload={"ticker": "PETR4"},
            data_as_of=now,
            knowledge_cutoff=now,
        )
        assert req.capability == "research"

    def test_knowledge_cutoff_after_data_as_of_rejected(self) -> None:
        with pytest.raises(ValueError, match="knowledge_cutoff cannot be after data_as_of"):
            AgentRunRequest(
                capability="research",
                input_payload={},
                data_as_of=datetime(2026, 1, 1, tzinfo=UTC),
                knowledge_cutoff=datetime(2026, 2, 1, tzinfo=UTC),
            )

    def test_naive_datetime_rejected(self) -> None:
        with pytest.raises(ValueError, match="timezone"):
            AgentRunRequest(
                capability="research",
                input_payload={},
                data_as_of=datetime(2026, 1, 1),
                knowledge_cutoff=datetime(2026, 1, 1),
            )

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(Exception):
            AgentRunRequest(
                capability="research",
                input_payload={},
                data_as_of=datetime(2026, 1, 1, tzinfo=UTC),
                knowledge_cutoff=datetime(2026, 1, 1, tzinfo=UTC),
                unexpected_field="x",
            )


# ---------------------------------------------------------------------------
# organization_uuid
# ---------------------------------------------------------------------------


class TestOrganizationUuid:
    def test_valid_uuid(self) -> None:
        org_id = uuid4()
        principal = MagicMock()
        principal.organization_id = org_id
        assert organization_uuid(principal) == org_id

    def test_none_raises_400(self) -> None:
        principal = MagicMock()
        principal.organization_id = None
        with pytest.raises(HTTPException) as exc_info:
            organization_uuid(principal)
        assert exc_info.value.status_code == 400
        assert "no organization_id" in exc_info.value.detail

    def test_invalid_uuid_raises_400(self) -> None:
        principal = MagicMock()
        principal.organization_id = "not-a-uuid"
        with pytest.raises(HTTPException) as exc_info:
            organization_uuid(principal)
        assert exc_info.value.status_code == 400
        assert "not a UUID" in exc_info.value.detail


# ---------------------------------------------------------------------------
# _mark_dispatched
# ---------------------------------------------------------------------------


class TestMarkDispatched:
    @pytest.mark.asyncio
    async def test_sets_state_and_commits(self) -> None:
        session = AsyncMock()
        outbox = MagicMock()
        await _mark_dispatched(session, outbox)
        assert outbox.state == "dispatched"
        assert outbox.dispatched_at is not None
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rolls_back_on_commit_error(self) -> None:
        session = AsyncMock()
        session.commit = AsyncMock(side_effect=Exception("db error"))
        outbox = MagicMock()
        await _mark_dispatched(session, outbox)
        session.rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# OperationStatusResponse model
# ---------------------------------------------------------------------------


class TestOperationStatusResponse:
    def test建造s_response(self) -> None:
        now = datetime.now(UTC)
        resp = OperationStatusResponse(
            operation_id=uuid4(),
            workflow_id="operation-abc",
            status="completed",
            created_at=now,
            updated_at=now,
        )
        assert resp.status == "completed"
        assert resp.result is None
        assert resp.error_code is None

    def test_with_result(self) -> None:
        now = datetime.now(UTC)
        resp = OperationStatusResponse(
            operation_id=uuid4(),
            workflow_id="operation-abc",
            status="completed",
            created_at=now,
            updated_at=now,
            result={"value": 42},
            error_code="E001",
            error_detail="something went wrong",
        )
        assert resp.result == {"value": 42}
        assert resp.error_code == "E001"


# ---------------------------------------------------------------------------
# AgentRunAccepted model
# ---------------------------------------------------------------------------


class TestAgentRunAccepted:
    def test建造s_accepted(self) -> None:
        now = datetime.now(UTC)
        resp = AgentRunAccepted(
            operation_id=str(uuid4()),
            workflow_id="operation-xyz",
            submitted_at=now,
        )
        assert resp.status == "accepted"
        assert resp.duplicate is False

    def test_duplicate(self) -> None:
        now = datetime.now(UTC)
        resp = AgentRunAccepted(
            operation_id=str(uuid4()),
            workflow_id="operation-xyz",
            submitted_at=now,
            status="pending",
            duplicate=True,
        )
        assert resp.duplicate is True
        assert resp.status == "pending"


# ---------------------------------------------------------------------------
# Route handler: get_operation_status
# ---------------------------------------------------------------------------


class TestGetOperationStatus:
    @pytest.mark.asyncio
    async def test_returns_operation(self) -> None:
        org_id = uuid4()
        op_id = uuid4()
        now = datetime.now(UTC)
        principal = MagicMock()
        principal.organization_id = org_id

        mock_op = MagicMock()
        mock_op.id = op_id
        mock_op.state = "completed"
        mock_op.created_at = now
        mock_op.updated_at = now
        mock_op.result_data = {"value": 42}
        mock_op.error_code = None
        mock_op.error_detail = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_op
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        resp = await get_operation_status(op_id, session, principal)
        assert resp.operation_id == op_id
        assert resp.status == "completed"
        assert resp.result == {"value": 42}

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self) -> None:
        org_id = uuid4()
        op_id = uuid4()
        principal = MagicMock()
        principal.organization_id = org_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await get_operation_status(op_id, session, principal)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Route handler: start_agent_run
# ---------------------------------------------------------------------------


def _mock_op(created_at: datetime | None = None) -> MagicMock:
    op = MagicMock()
    op.id = uuid4()
    op.state = "accepted"
    op.created_at = created_at or datetime.now(UTC)
    return op


class TestStartAgentRun:
    @pytest.mark.asyncio
    async def test_new_run_accepted(self) -> None:
        org_id = uuid4()
        now = datetime.now(UTC)
        principal = MagicMock()
        principal.organization_id = org_id
        principal.subject = "user-1"

        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        session.commit = AsyncMock()

        mock_temporal = AsyncMock()
        mock_temporal.start_workflow = AsyncMock()

        payload = AgentRunRequest(
            capability="research",
            input_payload={"ticker": "PETR4"},
            data_as_of=datetime(2026, 1, 1, tzinfo=UTC),
            knowledge_cutoff=datetime(2026, 1, 1, tzinfo=UTC),
        )
        mock_request = MagicMock()
        mock_request.scope = {"type": "http"}

        with patch("apps.api.routes.institutional.create_domain_audit_entry", new_callable=AsyncMock):
            with patch(
                "apps.api.routes.institutional.select",
                return_value=MagicMock(where=MagicMock(return_value=MagicMock())),
            ):
                with patch("apps.api.routes.institutional.Operation", return_value=_mock_op(now)):
                    with patch("apps.api.routes.institutional.OperationDispatchOutbox", return_value=MagicMock()):
                        resp = await start_agent_run(
                            payload=payload,
                            request=mock_request,
                            session=session,
                            principal=principal,
                            idempotency_key="test-key-12345678",
                            temporal=mock_temporal,
                        )
        assert resp.status == "accepted"
        assert resp.duplicate is False

    @pytest.mark.asyncio
    async def test_duplicate_returns_existing(self) -> None:
        org_id = uuid4()
        op_id = uuid4()
        now = datetime.now(UTC)
        principal = MagicMock()
        principal.organization_id = org_id
        principal.subject = "user-1"

        request_data = {
            "organization_id": str(org_id),
            "requested_by": "user-1",
            "capability": "research",
            "case_id": None,
            "input_payload": {"ticker": "PETR4"},
            "data_as_of": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
            "knowledge_cutoff": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
        }
        request_hash = hashlib.sha256(
            json.dumps(request_data, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

        mock_existing = MagicMock()
        mock_existing.id = op_id
        mock_existing.request_hash = request_hash
        mock_existing.state = "pending"
        mock_existing.created_at = now

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_existing
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        payload = AgentRunRequest(
            capability="research",
            input_payload={"ticker": "PETR4"},
            data_as_of=datetime(2026, 1, 1, tzinfo=UTC),
            knowledge_cutoff=datetime(2026, 1, 1, tzinfo=UTC),
        )
        mock_request = MagicMock()
        mock_request.scope = {"type": "http"}

        with patch(
            "apps.api.routes.institutional.select", return_value=MagicMock(where=MagicMock(return_value=MagicMock()))
        ):
            resp = await start_agent_run(
                payload=payload,
                request=mock_request,
                session=session,
                principal=principal,
                idempotency_key="test-key-12345678",
                temporal=None,
            )
        assert resp.duplicate is True

    @pytest.mark.asyncio
    async def test_idempotency_conflict_different_hash(self) -> None:
        org_id = uuid4()
        principal = MagicMock()
        principal.organization_id = org_id
        principal.subject = "user-1"

        mock_existing = MagicMock()
        mock_existing.request_hash = "different-hash"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_existing
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        payload = AgentRunRequest(
            capability="research",
            input_payload={"ticker": "PETR4"},
            data_as_of=datetime(2026, 1, 1, tzinfo=UTC),
            knowledge_cutoff=datetime(2026, 1, 1, tzinfo=UTC),
        )
        mock_request = MagicMock()
        mock_request.scope = {"type": "http"}

        with patch(
            "apps.api.routes.institutional.select", return_value=MagicMock(where=MagicMock(return_value=MagicMock()))
        ):
            with pytest.raises(HTTPException) as exc_info:
                await start_agent_run(
                    payload=payload,
                    request=mock_request,
                    session=session,
                    principal=principal,
                    idempotency_key="test-key-12345678",
                    temporal=None,
                )
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_temporal_workflow_started(self) -> None:
        org_id = uuid4()
        now = datetime.now(UTC)
        principal = MagicMock()
        principal.organization_id = org_id
        principal.subject = "user-1"

        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        session.commit = AsyncMock()

        mock_temporal = AsyncMock()
        mock_temporal.start_workflow = AsyncMock()

        mock_request = MagicMock()
        mock_request.scope = {"type": "http"}

        with patch("apps.api.routes.institutional.create_domain_audit_entry", new_callable=AsyncMock):
            with patch(
                "apps.api.routes.institutional.select",
                return_value=MagicMock(where=MagicMock(return_value=MagicMock())),
            ):
                with patch("apps.api.routes.institutional.Operation", return_value=_mock_op(now)):
                    with patch("apps.api.routes.institutional.OperationDispatchOutbox", return_value=MagicMock()):
                        payload = AgentRunRequest(
                            capability="research",
                            input_payload={"ticker": "PETR4"},
                            data_as_of=datetime(2026, 1, 1, tzinfo=UTC),
                            knowledge_cutoff=datetime(2026, 1, 1, tzinfo=UTC),
                        )
                        resp = await start_agent_run(
                            payload=payload,
                            request=mock_request,
                            session=session,
                            principal=principal,
                            idempotency_key="test-key-12345678",
                            temporal=mock_temporal,
                        )
                        assert resp.status == "accepted"
                        mock_temporal.start_workflow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_temporal_workflow_already_started_error(self) -> None:
        from temporalio.exceptions import WorkflowAlreadyStartedError

        org_id = uuid4()
        now = datetime.now(UTC)
        principal = MagicMock()
        principal.organization_id = org_id
        principal.subject = "user-1"

        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        session.commit = AsyncMock()

        mock_temporal = AsyncMock()
        mock_temporal.start_workflow = AsyncMock(side_effect=WorkflowAlreadyStartedError("wf-1", "RunAgentWorkflow"))

        mock_request = MagicMock()
        mock_request.scope = {"type": "http"}

        with patch("apps.api.routes.institutional.create_domain_audit_entry", new_callable=AsyncMock):
            with patch(
                "apps.api.routes.institutional.select",
                return_value=MagicMock(where=MagicMock(return_value=MagicMock())),
            ):
                with patch("apps.api.routes.institutional.Operation", return_value=_mock_op(now)):
                    with patch("apps.api.routes.institutional.OperationDispatchOutbox", return_value=MagicMock()):
                        payload = AgentRunRequest(
                            capability="research",
                            input_payload={"ticker": "PETR4"},
                            data_as_of=datetime(2026, 1, 1, tzinfo=UTC),
                            knowledge_cutoff=datetime(2026, 1, 1, tzinfo=UTC),
                        )
                        resp = await start_agent_run(
                            payload=payload,
                            request=mock_request,
                            session=session,
                            principal=principal,
                            idempotency_key="test-key-12345678",
                            temporal=mock_temporal,
                        )
                        assert resp.status == "accepted"

    @pytest.mark.asyncio
    async def test_temporal_dispatch_failure_still_returns_accepted(self) -> None:
        org_id = uuid4()
        now = datetime.now(UTC)
        principal = MagicMock()
        principal.organization_id = org_id
        principal.subject = "user-1"

        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        session.commit = AsyncMock()

        mock_temporal = AsyncMock()
        mock_temporal.start_workflow = AsyncMock(side_effect=Exception("connection lost"))

        mock_request = MagicMock()
        mock_request.scope = {"type": "http"}

        with patch("apps.api.routes.institutional.create_domain_audit_entry", new_callable=AsyncMock):
            with patch(
                "apps.api.routes.institutional.select",
                return_value=MagicMock(where=MagicMock(return_value=MagicMock())),
            ):
                with patch("apps.api.routes.institutional.Operation", return_value=_mock_op(now)):
                    with patch("apps.api.routes.institutional.OperationDispatchOutbox", return_value=MagicMock()):
                        payload = AgentRunRequest(
                            capability="research",
                            input_payload={"ticker": "PETR4"},
                            data_as_of=datetime(2026, 1, 1, tzinfo=UTC),
                            knowledge_cutoff=datetime(2026, 1, 1, tzinfo=UTC),
                        )
                        resp = await start_agent_run(
                            payload=payload,
                            request=mock_request,
                            session=session,
                            principal=principal,
                            idempotency_key="test-key-12345678",
                            temporal=mock_temporal,
                        )
                        assert resp.status == "accepted"

    @pytest.mark.asyncio
    async def test_integrity_error_concurrent_insert_same_hash(self) -> None:
        org_id = uuid4()
        op_id = uuid4()
        now = datetime.now(UTC)
        principal = MagicMock()
        principal.organization_id = org_id
        principal.subject = "user-1"

        request_data = {
            "organization_id": str(org_id),
            "requested_by": "user-1",
            "capability": "research",
            "case_id": None,
            "input_payload": {"ticker": "PETR4"},
            "data_as_of": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
            "knowledge_cutoff": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
        }
        request_hash = hashlib.sha256(
            json.dumps(request_data, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

        mock_concurrent = MagicMock()
        mock_concurrent.id = op_id
        mock_concurrent.request_hash = request_hash
        mock_concurrent.state = "pending"
        mock_concurrent.created_at = now

        retry_result = MagicMock()
        retry_result.scalar_one_or_none.return_value = mock_concurrent

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                result = MagicMock()
                result.scalar_one_or_none.return_value = None
                return result
            else:
                return retry_result

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock(side_effect=IntegrityError("dup", {}, None))
        session.rollback = AsyncMock()

        mock_request = MagicMock()
        mock_request.scope = {"type": "http"}

        with patch("apps.api.routes.institutional.create_domain_audit_entry", new_callable=AsyncMock):
            with patch(
                "apps.api.routes.institutional.select",
                return_value=MagicMock(where=MagicMock(return_value=MagicMock())),
            ):
                with patch("apps.api.routes.institutional.Operation", return_value=_mock_op(now)):
                    with patch("apps.api.routes.institutional.OperationDispatchOutbox", return_value=MagicMock()):
                        payload = AgentRunRequest(
                            capability="research",
                            input_payload={"ticker": "PETR4"},
                            data_as_of=datetime(2026, 1, 1, tzinfo=UTC),
                            knowledge_cutoff=datetime(2026, 1, 1, tzinfo=UTC),
                        )
                        resp = await start_agent_run(
                            payload=payload,
                            request=mock_request,
                            session=session,
                            principal=principal,
                            idempotency_key="test-key-12345678",
                            temporal=None,
                        )
                        assert resp.duplicate is True
