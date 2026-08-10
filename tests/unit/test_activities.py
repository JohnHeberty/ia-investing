from __future__ import annotations

import pytest
from temporalio.exceptions import ApplicationError

from ia_investing.orchestration.activities.data_ingestion import parse_cvm_csv
from ia_investing.orchestration.activities.notifications import publish_event


def test_parse_cvm_activity_rejects_missing_required_fields() -> None:
    with pytest.raises(ApplicationError) as exc_info:
        parse_cvm_csv([{"cnpj": "1"}], 1000)

    assert exc_info.value.non_retryable is True
    assert exc_info.value.type == "DataValidationError"


def test_publish_event_is_idempotent_for_canonical_payload() -> None:
    first = publish_event("cvm.ingested", {"year": 2025, "issuer": "1"})
    second = publish_event("cvm.ingested", {"issuer": "1", "year": 2025})

    assert first == second
