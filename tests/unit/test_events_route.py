from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from apps.api.routes.events import router


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


class TestEventsRoute:
    def test_post_accepts_valid_batch(self, client: TestClient) -> None:
        payload = {
            "events": [
                {
                    "event": "page_view",
                    "path": "/dashboard",
                    "timestamp": int(time.time() * 1000),
                },
                {
                    "event": "button_click",
                    "target": "submit-btn",
                    "path": "/settings",
                    "timestamp": int(time.time() * 1000),
                    "metadata": {"form": "profile"},
                },
            ]
        }
        resp = client.post("/api/v1/events", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["count"] == "2"

    def test_post_accepts_empty_batch(self, client: TestClient) -> None:
        resp = client.post("/api/v1/events", json={"events": []})
        assert resp.status_code == 200
        assert resp.json()["count"] == "0"

    def test_post_rejects_invalid_payload(self, client: TestClient) -> None:
        resp = client.post("/api/v1/events", json={"not_events": []})
        assert resp.status_code == 422

    def test_post_rejects_event_missing_required_field(self, client: TestClient) -> None:
        payload = {"events": [{"path": "/x", "timestamp": 1}]}
        resp = client.post("/api/v1/events", json=payload)
        assert resp.status_code == 422

    def test_post_logs_telemetry_events(self, client: TestClient) -> None:
        payload = {
            "events": [
                {"event": "click", "path": "/", "timestamp": 1000},
            ]
        }
        with patch("apps.api.routes.events.logger") as mock_logger:
            client.post("/api/v1/events", json=payload)
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert call_args[0][0] == "telemetry_event"
            assert call_args[1]["event_type"] == "click"
            assert call_args[1]["path"] == "/"

    def test_post_rejects_batch_over_max_length(self, client: TestClient) -> None:
        events = [
            {"event": "e", "path": "/", "timestamp": 1000}
            for _ in range(101)
        ]
        resp = client.post("/api/v1/events", json={"events": events})
        assert resp.status_code == 422
