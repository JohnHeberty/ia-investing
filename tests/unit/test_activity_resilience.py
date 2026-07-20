from __future__ import annotations

import asyncio
from typing import Any

import pytest
from temporalio.exceptions import ApplicationError

from ia_investing.ai.provider import MockProvider
from ia_investing.orchestration.activities.data_ingestion import parse_cvm_csv
from ia_investing.orchestration.activities.notifications import publish_event
from ia_investing.orchestration.activities.research_mock import (
    calculate_screening_metrics,
    generate_discovery_briefs,
    identify_anomalies,
    run_critic_agent,
    run_filing_analyst,
    run_news_analyst,
)


def test_publish_event_deterministic_same_output() -> None:
    """publish_event returns same event_id for same logical payload regardless of key order."""
    first = publish_event("cvm.ingested", {"year": 2025, "issuer": "1"})
    second = publish_event("cvm.ingested", {"issuer": "1", "year": 2025})

    assert first == second
    assert len(first) == 64


def test_publish_event_different_for_different_payload() -> None:
    """publish_event returns different event_id for different payloads."""
    first = publish_event("cvm.ingested", {"year": 2025, "issuer": "1"})
    second = publish_event("cvm.ingested", {"year": 2026, "issuer": "1"})

    assert first != second


def test_mock_filing_analyst_deterministic() -> None:
    """run_filing_analyst returns identical output on repeated calls."""
    first = run_filing_analyst("issuer-1", "Issuer", {}, {})
    second = run_filing_analyst("issuer-1", "Issuer", {}, {})

    assert first == second
    assert first["critic_notes"] == "Deterministic phase-1 mock output."
    assert first["verdict"] == "neutral"
    assert first["confidence"] == 0.5


def test_mock_news_analyst_deterministic() -> None:
    """run_news_analyst returns identical output on repeated calls."""
    first = run_news_analyst("news-1", "Title", "Body", "https://example.com")
    second = run_news_analyst("news-1", "Title", "Body", "https://example.com")

    assert first == second
    assert first.news_item_id == "news-1"
    assert first.event_type == "unknown"


def test_critic_agent_validates_required_fields() -> None:
    """run_critic_agent raises ValueError when analyst output is missing required fields."""
    incomplete_output: dict[str, Any] = {
        "issuer_id": "issuer-1",
        "verdict": "positive",
    }

    with pytest.raises(KeyError):
        run_critic_agent(incomplete_output, {}, {})


def test_parse_cvm_csv_rejects_negative_scale() -> None:
    """parse_cvm_csv raises ApplicationError for non-positive scale_factor."""
    with pytest.raises(ApplicationError) as exc_info:
        parse_cvm_csv([{"cnpj": "1", "dt_referencia": "2025-01-01", "cod_conta": "3.01", "valor": 100}], 0)

    assert exc_info.value.non_retryable is True
    assert exc_info.value.type == "DataValidationError"


def test_parse_cvm_csv_rejects_missing_fields() -> None:
    """parse_cvm_csv raises ApplicationError when records lack required fields."""
    with pytest.raises(ApplicationError) as exc_info:
        parse_cvm_csv([{"cnpj": "1"}], 1000)

    assert exc_info.value.non_retryable is True
    assert "missing required fields" in str(exc_info.value)


def test_generate_discovery_briefs_empty_input() -> None:
    """generate_discovery_briefs handles empty scored list gracefully."""
    result = generate_discovery_briefs([], {})

    assert result == []
    assert isinstance(result, list)


def test_calculate_screening_metrics_preserves_existing_score() -> None:
    """calculate_screening_metrics preserves screening_score if already present."""
    scored = calculate_screening_metrics([{"issuer_id": "issuer-1", "screening_score": 0.75}])

    assert len(scored) == 1
    assert scored[0]["screening_score"] == 0.75


def test_identify_anomalies_empty_input() -> None:
    """identify_anomalies handles empty scored list."""
    result = identify_anomalies([])

    assert result == {}


def test_mock_provider_deterministic_output() -> None:
    """MockProvider produces same output for same input key."""
    payload: dict[str, object] = {"question": "What is the revenue?"}
    key = MockProvider.request_key("gpt-4", "You are a financial analyst.", payload)
    provider = MockProvider({key: {"answer": "Revenue is BRL 10B."}})

    first_result = asyncio.get_event_loop().run_until_complete(
        provider.complete(
            model="gpt-4",
            instructions="You are a financial analyst.",
            input_payload=payload,
            output_schema={},
        )
    )
    second_result = asyncio.get_event_loop().run_until_complete(
        provider.complete(
            model="gpt-4",
            instructions="You are a financial analyst.",
            input_payload=payload,
            output_schema={},
        )
    )

    assert first_result == second_result
    assert first_result.output == {"answer": "Revenue is BRL 10B."}
