"""Tests for apps.api.routes.agent_runtime — agent run CRUD and approvals."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.api.routes.agent_runtime import (
    AgentRunV1,
    ApprovalDecisionV1,
    ApprovalV1,
    CreateAgentRunV1,
)

# ---------------------------------------------------------------------------
# Pydantic model validation
# ---------------------------------------------------------------------------


class TestCreateAgentRunV1:
    def test_valid_payload(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        body = CreateAgentRunV1(
            capability="research_stock",
            input={"ticker": "PETR4"},
            data_as_of=now,
            knowledge_cutoff=now,
        )
        assert body.capability == "research_stock"

    def test_invalid_capability_pattern(self) -> None:
        with pytest.raises(Exception):
            CreateAgentRunV1(
                capability="INVALID-CAP!",
                input={},
                data_as_of=datetime.now(UTC),
                knowledge_cutoff=datetime.now(UTC),
            )

    def test_capability_with_underscores(self) -> None:
        body = CreateAgentRunV1(
            capability="my_capability_123",
            input={},
            data_as_of=datetime.now(UTC),
            knowledge_cutoff=datetime.now(UTC),
        )
        assert body.capability == "my_capability_123"

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(Exception):
            CreateAgentRunV1(
                capability="research",
                input={},
                data_as_of=datetime.now(UTC),
                knowledge_cutoff=datetime.now(UTC),
                surprise=True,
            )

    def test_optional_case_id(self) -> None:
        body = CreateAgentRunV1(
            capability="research",
            input={},
            data_as_of=datetime.now(UTC),
            knowledge_cutoff=datetime.now(UTC),
            case_id=uuid4(),
        )
        assert body.case_id is not None

    def test_optional_version_pin(self) -> None:
        body = CreateAgentRunV1(
            capability="research",
            input={},
            data_as_of=datetime.now(UTC),
            knowledge_cutoff=datetime.now(UTC),
            version_pin=uuid4(),
        )
        assert body.version_pin is not None


class TestAgentRunV1:
    def test建造s_from_attributes(self) -> None:
        now = datetime.now(UTC)
        run = AgentRunV1(
            id=uuid4(),
            capability_id=uuid4(),
            agent_version_id=uuid4(),
            case_id=None,
            workflow_id="wf-1",
            trace_id="abc123",
            input_sha256="a" * 64,
            output_payload=None,
            data_as_of=now,
            knowledge_cutoff=now,
            status="completed",
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=Decimal("0.01"),
            duration_ms=5000,
            evidence_coverage=Decimal("0.95"),
            error_code=None,
            error_detail=None,
            created_at=now,
        )
        assert run.status == "completed"
        assert run.cost_usd == Decimal("0.01")


class TestApprovalDecisionV1:
    def test_valid_approved(self) -> None:
        body = ApprovalDecisionV1(decision="approved", reason="looks good")
        assert body.decision == "approved"

    def test_valid_rejected(self) -> None:
        body = ApprovalDecisionV1(decision="rejected", reason="too risky")
        assert body.decision == "rejected"

    def test_invalid_decision(self) -> None:
        with pytest.raises(Exception):
            ApprovalDecisionV1(decision="maybe", reason="idk")

    def test_empty_reason_rejected(self) -> None:
        with pytest.raises(Exception):
            ApprovalDecisionV1(decision="approved", reason="")


class TestApprovalV1:
    def test建造s_approval(self) -> None:
        now = datetime.now(UTC)
        approval = ApprovalV1(
            id=uuid4(),
            run_id=uuid4(),
            tool_call_id=uuid4(),
            scope="portfolio_rebalance",
            impact={"weight_change": 0.05},
            requested_by="user-1",
            requested_at=now,
            expires_at=now,
            status="pending",
            decided_by=None,
            decision_reason=None,
            decided_at=None,
        )
        assert approval.status == "pending"
        assert approval.decided_by is None
