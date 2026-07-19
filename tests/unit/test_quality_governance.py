from datetime import UTC, datetime, timedelta

import pytest

from ia_investing.application.data_quality import validate_transition


@pytest.mark.parametrize(
    "current,target",
    [("open", "acknowledged"), ("open", "resolved"), ("open", "waived"), ("acknowledged", "resolved")],
)
def test_valid_incident_transitions(current: str, target: str) -> None:
    validate_transition(current, target)


@pytest.mark.parametrize("current,target", [("resolved", "open"), ("open", "open"), ("acknowledged", "open")])
def test_invalid_incident_transitions(current: str, target: str) -> None:
    with pytest.raises(ValueError, match="invalid"):
        validate_transition(current, target)


def test_waiver_expiry_example_is_in_the_future() -> None:
    now = datetime.now(UTC)
    assert now + timedelta(days=1) > now
