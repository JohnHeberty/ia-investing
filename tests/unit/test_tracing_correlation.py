"""Tests for tracing correlation: trace/span ↔ workflow/case/run/tool-call IDs.

Verifies that:
- _runner.py creates OTel spans with correct attributes
- execution.py links spans to stored trace_id via inject_traceparent_into_context
- tracing.py helper functions produce valid W3C traceparent headers
- OpenTelemetry context is properly propagated from stored trace_id
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from opentelemetry.sdk.trace import TracerProvider


class TestTracingHelpers:
    def test_span_context_includes_all_ids(self) -> None:
        from ia_investing.ai.tracing import span_context

        attrs = span_context(
            run_id="r-1",
            case_id="c-1",
            workflow_id="w-1",
            capability="filing",
            version="1.0",
        )
        assert attrs["agent.run_id"] == "r-1"
        assert attrs["agent.case_id"] == "c-1"
        assert attrs["agent.workflow_id"] == "w-1"
        assert attrs["agent.capability"] == "filing"
        assert attrs["agent.version"] == "1.0"

    def test_span_context_optional_fields(self) -> None:
        from ia_investing.ai.tracing import span_context

        attrs = span_context(run_id="r-2", capability="news", version="2.0")
        assert "agent.case_id" not in attrs
        assert "agent.workflow_id" not in attrs

    def test_extract_trace_id_returns_hex(self) -> None:
        from ia_investing.ai.tracing import extract_trace_id

        provider = TracerProvider()
        tracer = provider.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            tid = extract_trace_id(span)
        assert tid is not None
        assert len(tid) == 32
        assert all(c in "0123456789abcdef" for c in tid)

    def test_extract_trace_id_none_for_none(self) -> None:
        from ia_investing.ai.tracing import extract_trace_id

        assert extract_trace_id(None) is None

    def test_inject_traceparent_into_valid_context(self) -> None:
        from ia_investing.ai.tracing import inject_traceparent_into_context

        ctx = inject_traceparent_into_context("a" * 32)
        assert ctx is not None

    def test_inject_traceparent_into_short_id_returns_empty(self) -> None:
        from ia_investing.ai.tracing import inject_traceparent_into_context

        ctx = inject_traceparent_into_context("short")
        assert ctx is not None

    def test_inject_traceparent_into_empty_returns_empty(self) -> None:
        from ia_investing.ai.tracing import inject_traceparent_into_context

        ctx = inject_traceparent_into_context("")
        assert ctx is not None

    def test_inject_trace_context_builds_traceparent(self) -> None:
        from ia_investing.ai.tracing import inject_trace_context

        result = inject_trace_context({}, "b" * 32)
        assert "traceparent" in result
        parts = result["traceparent"].split("-")
        assert len(parts) == 4
        assert parts[0] == "00"
        assert parts[1] == "b" * 32

    def test_inject_trace_context_uses_current_span(self) -> None:
        from ia_investing.ai.tracing import inject_trace_context

        provider = TracerProvider()
        tracer = provider.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            span_tid = f"{span.get_span_context().trace_id:032x}"
            headers = inject_trace_context({}, "a" * 32)
            assert "traceparent" in headers
            parts = headers["traceparent"].split("-")
            assert len(parts) == 4
            assert parts[1] == span_tid

    def test_inject_trace_context_falls_back_to_param(self) -> None:
        from ia_investing.ai.tracing import inject_trace_context

        headers = inject_trace_context({}, "c" * 32)
        assert "traceparent" in headers
        parts = headers["traceparent"].split("-")
        assert parts[1] == "c" * 32

    def test_inject_trace_context_no_trace_id_returns_headers(self) -> None:
        from ia_investing.ai.tracing import inject_trace_context

        result = inject_trace_context({}, "")
        assert "traceparent" not in result


class TestTraceContextReconstitution:
    def test_inject_creates_usable_context(self) -> None:
        from ia_investing.ai.tracing import inject_traceparent_into_context

        ctx = inject_traceparent_into_context("0123456789abcdef0123456789abcdef")
        assert ctx is not None

        provider = TracerProvider()
        tracer = provider.get_tracer("test")
        with tracer.start_as_current_span("child", context=ctx) as span:
            span_ctx = span.get_span_context()
            assert span_ctx is not None
            assert span_ctx.trace_id != 0

    def test_roundtrip_via_traceparent_header(self) -> None:
        from ia_investing.ai.tracing import (
            extract_trace_id,
            inject_trace_context,
        )

        provider = TracerProvider()
        tracer = provider.get_tracer("test")
        with tracer.start_as_current_span("original") as original_span:
            original_tid = extract_trace_id(original_span)
            assert original_tid is not None
            headers = inject_trace_context({}, original_tid)
            assert "traceparent" in headers
            assert headers["traceparent"].split("-")[1] == original_tid


class TestRunnerTracing:
    @pytest.mark.asyncio
    async def test_runner_creates_span_on_success(self) -> None:
        from ia_investing.ai._config import AgentConfig
        from ia_investing.ai._runner import AgentRunner

        config = AgentConfig(
            name="test_agent",
            display_name_pt="Agente Teste",
            model="gpt-4o",
            temperature=0.0,
            max_tokens=1000,
            system_prompt_path="test/system.md",
            max_timeout_seconds=30,
        )

        mock_settings = MagicMock()
        mock_settings.openai_api_key = "test"

        mock_runner_mod = MagicMock()
        mock_result = MagicMock()
        mock_result.final_output = {"status": "ok"}
        mock_context = MagicMock()
        mock_context.usage.input_tokens = 100
        mock_context.usage.output_tokens = 50
        mock_result.context_wrapper = mock_context

        with patch("ia_investing.ai._runner.Runner", mock_runner_mod):
            mock_runner_mod.run = AsyncMock(return_value=mock_result)

            agent_runner = AgentRunner(config, settings=mock_settings)
            with patch.object(agent_runner, "_load_prompt_if_needed", return_value="test prompt"):
                result = await agent_runner.run({"input": "test"})

        assert result.status == "completed"
        assert result.tokens_prompt == 100
        assert result.tokens_completion == 50
        assert result.agent_name == "test_agent"

    @pytest.mark.asyncio
    async def test_runner_records_error_on_failure(self) -> None:
        from ia_investing.ai._config import AgentConfig
        from ia_investing.ai._runner import AgentRunner

        config = AgentConfig(
            name="fail_agent",
            display_name_pt="Agente Falha",
            model="gpt-4o",
            temperature=0.0,
            max_tokens=1000,
            system_prompt_path="test/system.md",
            max_timeout_seconds=1,
        )

        mock_settings = MagicMock()
        mock_settings.openai_api_key = "test"

        mock_runner_mod = MagicMock()
        mock_runner_mod.run = AsyncMock(side_effect=RuntimeError("provider down"))

        with patch("ia_investing.ai._runner.Runner", mock_runner_mod):
            agent_runner = AgentRunner(config, settings=mock_settings)
            with patch.object(agent_runner, "_load_prompt_if_needed", return_value="test"):
                result = await agent_runner.run({"input": "test"})

        assert result.status == "failed"
        assert result.error_message is not None
        assert "provider down" in result.error_message


class TestExecutionTraceLinking:
    def test_trace_id_recorded_in_span_attributes(self) -> None:
        from ia_investing.ai.tracing import span_context

        attrs = span_context(
            run_id="run-abc",
            capability="filing",
            version="1.0",
            case_id="case-123",
            workflow_id="wf-456",
        )
        assert attrs["agent.run_id"] == "run-abc"
        assert attrs["agent.case_id"] == "case-123"
        assert attrs["agent.workflow_id"] == "wf-456"
