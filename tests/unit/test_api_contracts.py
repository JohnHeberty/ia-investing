from apps.api.main import app


def test_agent_run_command_is_async_and_idempotent_in_openapi() -> None:
    operation = app.openapi()["paths"]["/api/v1/agent-runs"]["post"]

    assert "202" in operation["responses"]
    idempotency_header = next(
        parameter for parameter in operation["parameters"] if parameter["name"] == "Idempotency-Key"
    )
    assert idempotency_header["required"] is True


def test_legacy_synchronous_agent_command_is_not_exposed() -> None:
    paths = app.openapi()["paths"]

    assert "post" not in paths["/api/v1/agents/runs"]
    assert "/api/v1/operations/{operation_id}" in paths


def test_research_commands_and_point_in_time_queries_are_exposed() -> None:
    paths = app.openapi()["paths"]
    expected = {
        "/api/v1/research/cases": {"get", "post"},
        "/api/v1/research/cases/{case_id}": {"get"},
        "/api/v1/research/cases/{case_id}/transitions": {"post"},
        "/api/v1/research/evidence/search": {"get"},
        "/api/v1/research/claims/{claim_id}/verification": {"post"},
        "/api/v1/research/cases/{case_id}/assessments": {"post"},
        "/api/v1/research/assessments/{assessment_id}/reviews": {"post"},
        "/api/v1/research/reviews/{review_request_id}/decision": {"post"},
        "/api/v1/research/theses": {"post"},
        "/api/v1/research/theses/{thesis_id}/versions": {"post"},
        "/api/v1/research/thesis-versions/{version_id}/activation": {"post"},
        "/api/v1/research/theses/{thesis_id}": {"get"},
        "/api/v1/research/valuations": {"post"},
        "/api/v1/research/valuations/{run_id}": {"get"},
    }

    for path, methods in expected.items():
        assert methods <= set(paths[path])

    transition_parameters = paths["/api/v1/research/cases/{case_id}/transitions"]["post"]["parameters"]
    revise_parameters = paths["/api/v1/research/theses/{thesis_id}/versions"]["post"]["parameters"]
    assert any(item["name"] == "If-Match" and item["required"] for item in transition_parameters)
    assert any(item["name"] == "If-Match" and item["required"] for item in revise_parameters)

    case_query_parameters = paths["/api/v1/research/cases"]["get"]["parameters"]
    assert {"state", "as_of", "after", "limit"} <= {item["name"] for item in case_query_parameters}
