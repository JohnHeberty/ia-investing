import pytest
from fastapi import HTTPException

from apps.api.routes.research import parse_etag
from ia_investing.application.research import required_permission


@pytest.mark.parametrize(
    "current,target,permission",
    [
        ("draft", "triage", "research_cases:submit"),
        ("triage", "in_research", "research_cases:assign"),
        ("in_research", "review", "research_cases:submit"),
        ("review", "approved", "research_cases:review"),
        ("approved", "closed", "research_cases:close"),
        ("closed", "triage", "research_cases:reopen"),
    ],
)
def test_research_case_transition_permissions(current: str, target: str, permission: str) -> None:
    assert required_permission(current, target) == permission


def test_research_case_rejects_invalid_transition() -> None:
    with pytest.raises(ValueError, match="invalid"):
        required_permission("draft", "approved")


@pytest.mark.parametrize("etag", ['"3"', 'W/"3"', "3"])
def test_research_etag_parsing(etag: str) -> None:
    assert parse_etag(etag) == 3


def test_invalid_research_etag_is_bad_request() -> None:
    with pytest.raises(HTTPException) as exc:
        parse_etag('"not-a-version"')
    assert exc.value.status_code == 400
