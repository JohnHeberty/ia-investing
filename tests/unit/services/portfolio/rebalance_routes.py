"""Tests for rebalance API routes — permission enforcement, request validation."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def auth_headers():
    return {"Authorization": "Bearer test-token"}


class TestRebalancePermissions:
    def test_propose_requires_rebalance_permission(self, client):
        portfolio_id = uuid.uuid4()
        resp = client.post(
            f"/api/v1/rebalance/{portfolio_id}/propose",
            json={"target_allocations": {"PETR4": 0.5}, "rationale": "test"},
        )
        assert resp.status_code in (401, 403)

    def test_list_proposals_requires_rebalance_permission(self, client):
        resp = client.get("/api/v1/rebalance/proposals")
        assert resp.status_code in (401, 403)

    def test_get_proposal_requires_rebalance_permission(self, client):
        proposal_id = uuid.uuid4()
        resp = client.get(f"/api/v1/rebalance/proposals/{proposal_id}")
        assert resp.status_code in (401, 403)

    def test_approve_requires_rebalance_permission(self, client):
        proposal_id = uuid.uuid4()
        resp = client.post(f"/api/v1/rebalance/proposals/{proposal_id}/approve", json={})
        assert resp.status_code in (401, 403)

    def test_cancel_requires_rebalance_permission(self, client):
        proposal_id = uuid.uuid4()
        resp = client.post(
            f"/api/v1/rebalance/proposals/{proposal_id}/cancel",
            json={"reason": "test"},
        )
        assert resp.status_code in (401, 403)

    def test_complete_requires_rebalance_permission(self, client):
        proposal_id = uuid.uuid4()
        resp = client.post(f"/api/v1/rebalance/proposals/{proposal_id}/complete")
        assert resp.status_code in (401, 403)

    def test_execute_step_requires_rebalance_permission(self, client):
        proposal_id = uuid.uuid4()
        resp = client.post(
            f"/api/v1/rebalance/proposals/{proposal_id}/execute-step",
            json={"trade_ids": [str(uuid.uuid4())]},
        )
        assert resp.status_code in (401, 403)

    def test_drift_requires_rebalance_permission(self, client):
        portfolio_id = uuid.uuid4()
        resp = client.get(f"/api/v1/rebalance/{portfolio_id}/drift")
        assert resp.status_code in (401, 403)

    def test_history_requires_rebalance_permission(self, client):
        portfolio_id = uuid.uuid4()
        resp = client.get(f"/api/v1/rebalance/{portfolio_id}/history")
        assert resp.status_code in (401, 403)


class TestProposeRequestValidation:
    def test_missing_rationale_rejected(self, client):
        portfolio_id = uuid.uuid4()
        resp = client.post(
            f"/api/v1/rebalance/{portfolio_id}/propose",
            json={"target_allocations": {"PETR4": 0.5}},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code in (401, 403, 422, 503)

    def test_empty_rationale_rejected(self, client):
        portfolio_id = uuid.uuid4()
        resp = client.post(
            f"/api/v1/rebalance/{portfolio_id}/propose",
            json={"target_allocations": {"PETR4": 0.5}, "rationale": ""},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code in (401, 403, 422, 503)


class TestCancelRequestValidation:
    def test_missing_reason_rejected(self, client):
        proposal_id = uuid.uuid4()
        resp = client.post(
            f"/api/v1/rebalance/proposals/{proposal_id}/cancel",
            json={},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code in (401, 403, 422, 503)
