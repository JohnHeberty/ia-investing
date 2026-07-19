from fastapi.testclient import TestClient

from apps.api.main import app


def test_http_errors_use_problem_details() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/operations/00000000-0000-4000-8000-000000000001")

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["title"] == "Unauthorized"
    assert response.json()["instance"].startswith("/api/v1/operations/")
