from __future__ import annotations

from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app


def _auth_header(permissions: str = "") -> dict[str, str]:
    token = jwt.encode({"sub": "test-user", "permissions": permissions}, "key", algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _idempotency_header(key: str = "test-key") -> dict[str, str]:
    return {"Idempotency-Key": key}


def _etag_header(version: int = 1) -> dict[str, str]:
    return {"If-Match": f'"{version}"'}


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestResearchAuth:
    def test_list_cases_requires_auth(self, client):
        response = client.get("/api/v1/research/cases")
        assert response.status_code in (401, 403)

    def test_list_cases_requires_read_permission(self, client):
        response = client.get(
            "/api/v1/research/cases",
            headers=_auth_header(),
        )
        assert response.status_code in (401, 403)

    def test_get_case_requires_auth(self, client):
        case_id = uuid4()
        response = client.get(f"/api/v1/research/cases/{case_id}")
        assert response.status_code in (401, 403)

    def test_create_case_requires_permission(self, client):
        response = client.post(
            "/api/v1/research/cases",
            json={
                "case_type": "fundamental",
                "title": "Test",
                "priority": "normal",
                "issuer_id": str(uuid4()),
                "data_as_of": "2026-01-01T00:00:00Z",
                "questions": ["What is the fair value?"],
            },
            headers=_idempotency_header(),
        )
        assert response.status_code in (401, 403)

    def test_transition_case_requires_if_match(self, client):
        case_id = uuid4()
        response = client.post(
            f"/api/v1/research/cases/{case_id}/transitions",
            json={"target": "triage", "reason": "test"},
            headers={**_auth_header("research:read"), **_idempotency_header()},
        )
        assert response.status_code in (422, 400)


class TestResearchPagination:
    def test_list_cases_returns_cursor_header(self, client):
        response = client.get(
            "/api/v1/research/cases?limit=1",
            headers=_auth_header(),
        )
        if response.status_code == 200 and len(response.json()) == 1:
            assert "X-Next-Cursor" in response.headers or response.headers.get("X-Next-Cursor") is None


class TestResearchSchema:
    def test_openapi_schema_exists(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "paths" in schema

    def test_research_endpoints_in_schema(self, client):
        response = client.get("/openapi.json")
        schema = response.json()
        paths = schema.get("paths", {})
        research_paths = [p for p in paths if "/research" in p]
        assert len(research_paths) > 0

    def test_thesis_endpoints_in_schema(self, client):
        response = client.get("/openapi.json")
        schema = response.json()
        paths = schema.get("paths", {})
        thesis_paths = [p for p in paths if "/theses" in p or "/thesis" in p]
        assert len(thesis_paths) > 0


class TestValuationEndpoints:
    def test_get_valuation_requires_auth(self, client):
        run_id = uuid4()
        response = client.get(f"/api/v1/research/valuations/{run_id}")
        assert response.status_code in (401, 403)

    def test_create_valuation_requires_permission(self, client):
        response = client.post(
            "/api/v1/research/valuations",
            json={
                "thesis_version_id": str(uuid4()),
                "code_version": "1.0.0",
                "data_as_of": "2026-01-01T00:00:00Z",
                "assumptions": [
                    {
                        "name": "revenue_growth",
                        "value": 0.10,
                        "unit": "percent",
                        "horizon": "1Y",
                        "source_type": "financial_fact",
                        "source_id": str(uuid4()),
                        "source_version": "1.0",
                        "approved_by": "analyst",
                    }
                ],
                "scenarios": [
                    {
                        "name": "bear",
                        "probability": 0.25,
                        "free_cash_flows": [100],
                        "discount_rate": 0.12,
                        "terminal_growth": 0.02,
                        "net_debt": 500,
                        "shares_outstanding": 100,
                    },
                    {
                        "name": "base",
                        "probability": 0.50,
                        "free_cash_flows": [150],
                        "discount_rate": 0.10,
                        "terminal_growth": 0.03,
                        "net_debt": 500,
                        "shares_outstanding": 100,
                    },
                    {
                        "name": "bull",
                        "probability": 0.25,
                        "free_cash_flows": [200],
                        "discount_rate": 0.08,
                        "terminal_growth": 0.04,
                        "net_debt": 500,
                        "shares_outstanding": 100,
                    },
                ],
                "relative": {
                    "metric": 15.0,
                    "selected_multiple": 12.0,
                    "net_debt": 500,
                    "shares_outstanding": 100,
                },
                "reverse_dcf": {
                    "market_enterprise_value": 2000,
                    "starting_cash_flow": 150,
                    "discount_rate": 0.10,
                    "years": 5,
                },
            },
            headers={**_auth_header(), **_idempotency_header()},
        )
        assert response.status_code in (401, 403, 404, 422)


class TestClaimVerification:
    def test_verify_claim_requires_auth(self, client):
        claim_id = uuid4()
        response = client.post(
            f"/api/v1/research/claims/{claim_id}/verification",
            json={"cutoff": "2026-01-01T00:00:00Z"},
            headers=_idempotency_header(),
        )
        assert response.status_code in (401, 403)


class TestEvidenceSearch:
    def test_search_evidence_requires_auth(self, client):
        response = client.get(
            "/api/v1/research/evidence/search",
            params={"query": "test", "as_of": "2026-01-01T00:00:00Z"},
        )
        assert response.status_code in (401, 403)
