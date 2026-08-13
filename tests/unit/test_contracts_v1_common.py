from __future__ import annotations

import pytest
from pydantic import ValidationError

from ia_investing.contracts.v1.common import (
    CalibrationStatusResponse,
    CommitteeFinalizeResponse,
    CommitteePublishResponse,
    CommitteeSessionCreatedResponse,
    CommitteeSessionDetailResponse,
    CommitteeSessionListItem,
    CommitteeVoteResponse,
    CommitteeVotingResponse,
    ComponentStatusResponse,
    ExecutionConfirmedResponse,
    ExecutionCreatedResponse,
    ExecutionDispatchedResponse,
    ExecutionFailedResponse,
    ExecutionListItem,
    ExecutionSettledResponse,
    ExecutionStateResponse,
    HealthCheckResponse,
    OverrideActiveResponse,
    OverrideResponse,
    PaginatedResponse,
    PortfolioCreatedResponse,
    PortfolioDetailResponse,
    PortfolioListItem,
    PortfolioOptimizationResponse,
    RebalanceHistoryItem,
    RebalanceProposalActionResponse,
    RebalanceProposalCreatedResponse,
    RebalanceProposalDetailResponse,
    RebalanceProposalListItem,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
ALL_MODELS = [
    (PaginatedResponse, {"items": [], "total": 0, "limit": 10, "offset": 0}),
    (HealthCheckResponse, {"status": "ok", "checks": {"db": "ok"}}),
    (
        CalibrationStatusResponse,
        {
            "components": {"c": 1},
            "gate_status": {"g": True},
            "uncalibrated": ["x"],
        },
    ),
    (
        ComponentStatusResponse,
        {
            "component": "c",
            "calibration_score": 0.9,
            "drift": {"v": 1.0},
            "reliability": [{"r": 1}],
            "gate": {"g": True},
        },
    ),
    (
        OverrideResponse,
        {
            "id": "1",
            "component": "c",
            "reason": "r",
            "created_at": "2026-01-01",
            "expires_at": "2026-02-01",
            "requested_by": "u",
        },
    ),
    (
        OverrideActiveResponse,
        {
            "id": "1",
            "component": "c",
            "reason": "r",
            "requested_by": "u",
            "created_at": "2026-01-01",
            "expires_at": "2026-02-01",
            "active": True,
        },
    ),
    (
        ExecutionCreatedResponse,
        {"id": "1", "order_id": "o1", "state": "created", "action": "buy", "quantity": "10"},
    ),
    (
        ExecutionListItem,
        {"id": "1", "order_id": "o1", "portfolio_id": "p1", "action": "buy", "quantity": "10", "state": "pending"},
    ),
    (ExecutionStateResponse, {"id": "1", "state": "pending"}),
    (ExecutionDispatchedResponse, {"id": "1", "state": "dispatched"}),
    (
        ExecutionConfirmedResponse,
        {"id": "1", "state": "confirmed", "filled_quantity": "10", "avg_price": "50.0"},
    ),
    (ExecutionFailedResponse, {"id": "1", "state": "failed", "reason": "timeout"}),
    (ExecutionSettledResponse, {"id": "1", "state": "settled"}),
    (
        CommitteeSessionCreatedResponse,
        {"id": "1", "state": "scheduled", "scheduled_at": "2026-01-01T10:00:00"},
    ),
    (
        CommitteeSessionListItem,
        {
            "id": "1",
            "state": "scheduled",
            "scheduled_at": "2026-01-01T10:00:00",
            "total_members": 5,
            "present_members": 3,
        },
    ),
    (CommitteeSessionDetailResponse, {"id": "1", "state": "scheduled"}),
    (CommitteeVotingResponse, {"id": "1", "state": "voting", "proposals": []}),
    (CommitteeVoteResponse, {"id": "1", "vote": "yes", "proposal_id": "p1"}),
    (
        CommitteeFinalizeResponse,
        {"id": "1", "state": "decided", "votes_in_favor": 3, "votes_against": 1},
    ),
    (CommitteePublishResponse, {"id": "1", "state": "published", "decision": "approve"}),
    (
        RebalanceProposalCreatedResponse,
        {
            "id": "1",
            "state": "draft",
            "portfolio_id": "p1",
            "target_allocations": {"A": 0.5},
            "rationale": "rebalance",
            "created_by": "system",
        },
    ),
    (
        RebalanceProposalListItem,
        {
            "id": "1",
            "state": "draft",
            "portfolio_id": "p1",
            "target_allocations": {"A": 0.5},
            "rationale": "rebalance",
            "created_by": "system",
        },
    ),
    (
        RebalanceProposalDetailResponse,
        {
            "id": "1",
            "state": "draft",
            "portfolio_id": "p1",
            "target_allocations": {"A": 0.5},
            "rationale": "rebalance",
            "created_by": "system",
        },
    ),
    (RebalanceProposalActionResponse, {"id": "1", "state": "approved"}),
    (RebalanceHistoryItem, {"id": "1", "state": "completed", "portfolio_id": "p1"}),
    (PortfolioCreatedResponse, {}),
    (
        PortfolioListItem,
        {"id": "1", "name": "Test", "is_paper_trading": True, "base_currency": "BRL"},
    ),
    (PortfolioDetailResponse, {"id": "1", "name": "Test", "positions": []}),
    (
        PortfolioOptimizationResponse,
        {
            "operation_id": "1",
            "status": "optimal",
            "weights": {"A": 0.5},
            "trades": [],
            "slacks": {},
            "diagnostics": {},
            "input_sha256": "a" * 64,
        },
    ),
]


# ---------------------------------------------------------------------------
# Tests: valid instantiation
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestValidInstantiation:
    @pytest.mark.parametrize("model_cls,data", ALL_MODELS, ids=lambda x: getattr(x, "__name__", str(x)))
    def test_instantiate_with_valid_data(self, model_cls, data):
        instance = model_cls(**data)
        for key, value in data.items():
            assert getattr(instance, key) == value


# ---------------------------------------------------------------------------
# Tests: extra="forbid"
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestExtraForbid:
    @pytest.mark.parametrize("model_cls,data", ALL_MODELS, ids=lambda x: getattr(x, "__name__", str(x)))
    def test_rejects_extra_fields(self, model_cls, data):
        with pytest.raises(ValidationError, match="extra"):
            model_cls(**data, unexpected_field="should_fail")


# ---------------------------------------------------------------------------
# Tests: frozen=True
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestFrozen:
    @pytest.mark.parametrize(
        "model_cls,data,field_name,default",
        [
            (PaginatedResponse, {"items": [], "total": 0, "limit": 10, "offset": 0}, "total", 0),
            (HealthCheckResponse, {"status": "ok", "checks": {}}, "status", "ok"),
            (ExecutionStateResponse, {"id": "1", "state": "s"}, "state", "s"),
        ],
    )
    def test_prevents_mutation(self, model_cls, data, field_name, default):
        instance = model_cls(**data)
        with pytest.raises(ValidationError):
            setattr(instance, field_name, "mutated")


# ---------------------------------------------------------------------------
# Tests: default values
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestDefaults:
    def test_execution_list_item_created_at_defaults_none(self):
        instance = ExecutionListItem(id="1", order_id="o", portfolio_id="p", action="buy", quantity="1", state="s")
        assert instance.created_at is None

    def test_execution_dispatched_response_dispatched_at_defaults_none(self):
        instance = ExecutionDispatchedResponse(id="1", state="s")
        assert instance.dispatched_at is None

    def test_execution_settled_response_settled_at_defaults_none(self):
        instance = ExecutionSettledResponse(id="1", state="s")
        assert instance.settled_at is None

    def test_committee_session_list_item_defaults(self):
        instance = CommitteeSessionListItem(
            id="1", state="s", total_members=0, present_members=0
        )
        assert instance.scheduled_at is None
        assert instance.created_at is None

    def test_committee_session_detail_response_defaults(self):
        instance = CommitteeSessionDetailResponse(id="1", state="s")
        assert instance.present_members is None

    def test_committee_publish_response_defaults(self):
        instance = CommitteePublishResponse(id="1", state="s", decision="approve")
        assert instance.published_at is None

    def test_portfolio_created_response_all_none(self):
        instance = PortfolioCreatedResponse()
        assert instance.id is None
        assert instance.name is None
        assert instance.is_paper_trading is None
        assert instance.base_currency is None


# ---------------------------------------------------------------------------
# Tests: serialization round-trip
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestSerializationRoundTrip:
    def test_paginated_response_roundtrip(self):
        original = PaginatedResponse(items=[1, 2], total=2, limit=10, offset=0)
        data = original.model_dump()
        restored = PaginatedResponse(**data)
        assert restored == original

    def test_health_check_response_roundtrip(self):
        original = HealthCheckResponse(status="ok", checks={"db": "ok", "cache": "warn"})
        data = original.model_dump()
        restored = HealthCheckResponse(**data)
        assert restored == original

    def test_portfolio_optimization_response_roundtrip(self):
        original = PortfolioOptimizationResponse(
            operation_id="op-1",
            status="optimal",
            weights={"PETR4": 0.3},
            trades=[],
            slacks={},
            diagnostics={},
            input_sha256="a" * 64,
        )
        data = original.model_dump()
        restored = PortfolioOptimizationResponse(**data)
        assert restored == original
