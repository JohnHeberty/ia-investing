"""Unit tests for ia_investing.ai.provider — MockProvider and helpers."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ia_investing.ai.gateway_errors import ProviderError
from ia_investing.ai.provider import MockProvider, uuid_from_output


@pytest.mark.unit
class TestMockProviderRequestKey:
    def test_deterministic(self):
        key1 = MockProvider.request_key("gpt-4", "instr", {"a": 1})
        key2 = MockProvider.request_key("gpt-4", "instr", {"a": 1})
        assert key1 == key2

    def test_different_inputs_different_keys(self):
        key1 = MockProvider.request_key("gpt-4", "instr1", {})
        key2 = MockProvider.request_key("gpt-4", "instr2", {})
        assert key1 != key2

    def test_is_hex(self):
        key = MockProvider.request_key("m", "i", {})
        assert all(c in "0123456789abcdef" for c in key)
        assert len(key) == 64


@pytest.mark.unit
class TestMockProviderComplete:
    @pytest.mark.asyncio
    async def test_exact_match(self):
        provider = MockProvider(
            responses={"abc123": {"answer": 42}}
        )
        # Monkey-patch the key lookup
        provider.responses = {}
        key = MockProvider.request_key("m", "i", {})
        provider.responses[key] = {"answer": 42}
        result = await provider.complete(
            model="m", instructions="i", input_payload={}, output_schema={}
        )
        assert result.output == {"answer": 42}
        assert result.usage.prompt_tokens == 0

    @pytest.mark.asyncio
    async def test_fallback_match(self):
        provider = MockProvider()
        provider.add_fallback("*", "*", {"fallback": True})
        result = await provider.complete(
            model="any", instructions="any", input_payload={}, output_schema={}
        )
        assert result.output == {"fallback": True}

    @pytest.mark.asyncio
    async def test_no_match_raises(self):
        provider = MockProvider()
        with pytest.raises(ProviderError, match="No replay fixture"):
            await provider.complete(
                model="m", instructions="i", input_payload={}, output_schema={}
            )

    @pytest.mark.asyncio
    async def test_partial_fallback(self):
        provider = MockProvider()
        provider.add_fallback("gpt-4", "*", {"matched": True})
        result = await provider.complete(
            model="gpt-4", instructions="other", input_payload={}, output_schema={}
        )
        assert result.output == {"matched": True}

    @pytest.mark.asyncio
    async def test_model_mismatch_no_fallback(self):
        provider = MockProvider()
        provider.add_fallback("gpt-4", "*", {"x": 1})
        with pytest.raises(ProviderError):
            await provider.complete(
                model="gpt-3.5", instructions="i", input_payload={}, output_schema={}
            )


@pytest.mark.unit
class TestUuidFromOutput:
    def test_deterministic(self):
        u1 = uuid_from_output({"a": 1})
        u2 = uuid_from_output({"a": 1})
        assert u1 == u2

    def test_prefix(self):
        result = uuid_from_output({})
        assert result.startswith("output:")

    def test_different_output_different_uuid(self):
        u1 = uuid_from_output({"a": 1})
        u2 = uuid_from_output({"a": 2})
        assert u1 != u2
