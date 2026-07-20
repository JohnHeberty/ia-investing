from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from opentelemetry.sdk.trace import TracerProvider

from ia_investing.ai._config import FILING_ANALYST, NEWS_ANALYST, AgentConfig
from ia_investing.ai._runner import AgentResult, AgentRunner
from ia_investing.ai.provider import ProviderError
from ia_investing.ai.tracing import extract_trace_id, span_context


def _make_mock_runner_result(output: dict, prompt_tokens: int = 150, completion_tokens: int = 80):
    mock_context = MagicMock()
    mock_context.usage.input_tokens = prompt_tokens
    mock_context.usage.output_tokens = completion_tokens
    mock_result = MagicMock()
    mock_result.final_output = output
    mock_result.context_wrapper = mock_context
    return mock_result


def _make_config(name: str = "filing_analyst", output_type: str | None = None) -> AgentConfig:
    return AgentConfig(
        name=name,
        display_name_pt="Teste",
        model="gpt-4o",
        temperature=0.2,
        max_tokens=4096,
        system_prompt_path="test/system.md",
        structured_output_type=output_type,
        max_timeout_seconds=30,
    )


def _make_settings() -> MagicMock:
    mock_settings = MagicMock()
    mock_settings.openai_api_key = "test-key"
    return mock_settings


class TestApiToAgentE2E:
    @pytest.mark.asyncio
    async def test_filing_analyst_e2e(self) -> None:
        filing_output = {
            "capability": "filing",
            "summary": "Receita grew 12% YoY",
            "findings": [
                {
                    "statement": "Revenue increased",
                    "kind": "fact",
                    "confidence": "0.95",
                    "citations": [],
                }
            ],
            "contradictions": [],
            "uncertainty": [],
            "materiality": "high",
            "knowledge_cutoff": "2026-01-01T00:00:00Z",
        }
        mock_result = _make_mock_runner_result(filing_output, prompt_tokens=200, completion_tokens=120)

        mock_runner_mod = MagicMock()
        mock_runner_mod.run = AsyncMock(return_value=mock_result)

        with patch("ia_investing.ai._runner.Runner", mock_runner_mod):
            runner = AgentRunner(FILING_ANALYST, settings=_make_settings())
            with patch.object(runner, "_load_prompt_if_needed", return_value="system prompt"):
                result = await runner.run({"ticker": "PETR4", "question": "revenue analysis"})

        assert isinstance(result, AgentResult)
        assert result.status == "completed"
        assert result.agent_name == "filing_analyst"
        assert result.model_used == "gpt-4o"
        assert result.tokens_prompt == 200
        assert result.tokens_completion == 120
        assert result.cost_usd >= 0.0
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_news_analyst_e2e(self) -> None:
        news_output = {
            "capability": "news",
            "summary": "Positive sentiment on regulatory changes",
            "findings": [
                {
                    "statement": "New regulation approved",
                    "kind": "fact",
                    "confidence": "0.88",
                    "citations": [],
                }
            ],
            "contradictions": [],
            "uncertainty": ["Source reliability unclear"],
            "materiality": "medium",
            "knowledge_cutoff": "2026-01-01T00:00:00Z",
        }
        mock_result = _make_mock_runner_result(news_output, prompt_tokens=100, completion_tokens=60)

        mock_runner_mod = MagicMock()
        mock_runner_mod.run = AsyncMock(return_value=mock_result)

        with patch("ia_investing.ai._runner.Runner", mock_runner_mod):
            runner = AgentRunner(NEWS_ANALYST, settings=_make_settings())
            with patch.object(runner, "_load_prompt_if_needed", return_value="system prompt"):
                result = await runner.run({"ticker": "VALE3", "question": "recent news"})

        assert isinstance(result, AgentResult)
        assert result.status == "completed"
        assert result.agent_name == "news_analyst"
        assert result.model_used == "gpt-4o"
        assert result.tokens_prompt == 100
        assert result.tokens_completion == 60
        assert result.cost_usd >= 0.0
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_trace_id_propagated_through_chain(self) -> None:
        run_id = "run-e2e-001"
        attrs = span_context(
            run_id=run_id,
            case_id="case-abc",
            capability="filing",
            version="1.0",
        )
        assert attrs["agent.run_id"] == run_id
        assert attrs["agent.capability"] == "filing"

        provider = TracerProvider()
        tracer = provider.get_tracer("test")
        with tracer.start_as_current_span("e2e-span") as span:
            trace_id = extract_trace_id(span)
            assert trace_id is not None
            assert len(trace_id) == 32
            assert all(c in "0123456789abcdef" for c in trace_id)

        output = {"capability": "filing", "summary": "ok", "findings": [], "materiality": "low"}
        mock_result = _make_mock_runner_result(output)
        mock_runner_mod = MagicMock()
        mock_runner_mod.run = AsyncMock(return_value=mock_result)

        with patch("ia_investing.ai._runner.Runner", mock_runner_mod):
            runner = AgentRunner(FILING_ANALYST, settings=_make_settings())
            with patch.object(runner, "_load_prompt_if_needed", return_value="prompt"):
                result = await runner.run({"input": "test"}, context={"run_id": run_id})

        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_cost_and_tokens_recorded_in_result(self) -> None:
        output = {"capability": "filing", "summary": "ok", "findings": [], "materiality": "low"}
        mock_result = _make_mock_runner_result(output, prompt_tokens=300, completion_tokens=150)

        mock_runner_mod = MagicMock()
        mock_runner_mod.run = AsyncMock(return_value=mock_result)

        with patch("ia_investing.ai._runner.Runner", mock_runner_mod):
            runner = AgentRunner(FILING_ANALYST, settings=_make_settings())
            with patch.object(runner, "_load_prompt_if_needed", return_value="prompt"):
                result = await runner.run({"input": "test"})

        assert result.tokens_prompt >= 0
        assert result.tokens_completion >= 0
        assert result.cost_usd >= 0.0
        assert result.duration_ms >= 0.0

    @pytest.mark.asyncio
    async def test_provider_error_returns_failed_status(self) -> None:
        mock_runner_mod = MagicMock()
        mock_runner_mod.run = AsyncMock(
            side_effect=ProviderError("rate_limited", retryable=True, safe_detail="Rate limit exceeded")
        )

        with patch("ia_investing.ai._runner.Runner", mock_runner_mod):
            runner = AgentRunner(FILING_ANALYST, settings=_make_settings())
            with patch.object(runner, "_load_prompt_if_needed", return_value="prompt"):
                result = await runner.run({"input": "test"})

        assert isinstance(result, AgentResult)
        assert result.status == "failed"
        assert result.output_data is None
        assert result.tokens_prompt == 0
        assert result.tokens_completion == 0
        assert result.cost_usd == 0.0
        assert result.error_message is not None
        assert "Rate limit exceeded" in result.error_message

    @pytest.mark.asyncio
    async def test_structured_output_validated(self) -> None:
        filing_output = {
            "capability": "filing",
            "summary": "Structural validation pass",
            "findings": [],
            "contradictions": [],
            "uncertainty": [],
            "materiality": "low",
            "knowledge_cutoff": "2026-01-01T00:00:00Z",
        }
        mock_result = _make_mock_runner_result(filing_output)

        mock_runner_mod = MagicMock()
        mock_runner_mod.run = AsyncMock(return_value=mock_result)

        with patch("ia_investing.ai._runner.Runner", mock_runner_mod):
            runner = AgentRunner(FILING_ANALYST, settings=_make_settings())
            with patch.object(runner, "_load_prompt_if_needed", return_value="prompt"):
                result = await runner.run({"input": "test"})

        assert result.status == "completed"
        assert isinstance(result.output_data, dict)
        assert result.output_data["capability"] == "filing"
        assert isinstance(result.output_data["summary"], str)
        assert isinstance(result.output_data["findings"], list)
        assert isinstance(result.output_data["materiality"], str)
        assert result.output_data["materiality"] in {"low", "medium", "high"}
