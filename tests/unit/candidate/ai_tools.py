from __future__ import annotations

import hashlib
import json
from uuid import uuid4

import pytest
from pydantic import BaseModel

from ia_investing.ai.contracts import CommandReceipt
from ia_investing.ai.tools import (
    FORBIDDEN_TOOL_NAMES,
    FinancialMetricsInput,
    FinancialMetricsOutput,
    ToolApprovalRequiredError,
    ToolPolicyError,
    ToolRegistry,
    TypedTool,
    command_receipt,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
class _DummyInput(BaseModel):
    query: str = "test"


class _DummyOutput(BaseModel):
    result: str = "ok"


async def _dummy_handler(inp: _DummyInput) -> _DummyOutput:
    return _DummyOutput(result=f"processed:{inp.query}")


class _SensitiveInput(BaseModel):
    action: str = "approve"


class _SensitiveOutput(BaseModel):
    status: str = "done"


async def _sensitive_handler(inp: _SensitiveInput) -> _SensitiveOutput:
    return _SensitiveOutput(status="confirmed")


def _make_tool(
    name: str = "test_tool",
    sensitive: bool = False,
) -> TypedTool[BaseModel, BaseModel]:
    if sensitive:
        return TypedTool(
            name=name,
            version=1,
            input_type=_SensitiveInput,
            output_type=_SensitiveOutput,
            handler=_sensitive_handler,
            sensitive=True,
        )
    return TypedTool(
        name=name,
        version=1,
        input_type=_DummyInput,
        output_type=_DummyOutput,
        handler=_dummy_handler,
        sensitive=sensitive,
    )


@pytest.fixture()
def registry() -> ToolRegistry:
    return ToolRegistry()


@pytest.fixture()
def registered_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(_make_tool("alpha"))
    reg.register(_make_tool("beta"))
    return reg


# ---------------------------------------------------------------------------
# Tests: ToolRegistry.register()
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestRegister:
    def test_register_adds_tool(self, registry: ToolRegistry):
        tool = _make_tool("my_tool")
        registry.register(tool)
        assert "my_tool" in registry._tools

    def test_register_normalizes_name(self, registry: ToolRegistry):
        tool = _make_tool("  My_Tool  ")
        registry.register(tool)
        assert "my_tool" in registry._tools

    def test_register_duplicate_raises(self, registry: ToolRegistry):
        registry.register(_make_tool("dup"))
        with pytest.raises(ValueError, match="already registered"):
            registry.register(_make_tool("dup"))

    def test_register_forbidden_exact_name(self, registry: ToolRegistry):
        for forbidden in FORBIDDEN_TOOL_NAMES:
            with pytest.raises(ToolPolicyError, match="Forbidden"):
                registry.register(_make_tool(forbidden))

    def test_register_forbidden_substring(self, registry: ToolRegistry):
        with pytest.raises(ToolPolicyError, match="Forbidden"):
            registry.register(_make_tool("my_sql_tool"))


# ---------------------------------------------------------------------------
# Tests: ToolRegistry.allowed()
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestAllowed:
    def test_allowed_returns_subset(self, registered_registry: ToolRegistry):
        result = registered_registry.allowed({"alpha"})
        assert set(result.keys()) == {"alpha"}

    def test_allowed_sorted(self, registered_registry: ToolRegistry):
        result = registered_registry.allowed({"beta", "alpha"})
        assert list(result.keys()) == ["alpha", "beta"]

    def test_allowed_unknown_raises(self, registered_registry: ToolRegistry):
        with pytest.raises(ToolPolicyError, match="Unknown"):
            registered_registry.allowed({"alpha", "nonexistent"})


# ---------------------------------------------------------------------------
# Tests: ToolRegistry.invoke()
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestInvoke:
    @pytest.mark.asyncio
    async def test_invoke_non_sensitive(self, registered_registry: ToolRegistry):
        result = await registered_registry.invoke(
            "alpha",
            {"query": "hello"},
            allowlist={"alpha"},
        )
        assert result == _DummyOutput(result="processed:hello")

    @pytest.mark.asyncio
    async def test_invoke_not_in_allowlist(self, registered_registry: ToolRegistry):
        with pytest.raises(ToolPolicyError, match="not allowed"):
            await registered_registry.invoke(
                "alpha",
                {"query": "hello"},
                allowlist=set(),
            )

    @pytest.mark.asyncio
    async def test_invoke_not_registered(self, registry: ToolRegistry):
        with pytest.raises(ToolPolicyError, match="not allowed"):
            await registry.invoke(
                "ghost",
                {},
                allowlist={"ghost"},
            )

    @pytest.mark.asyncio
    async def test_invoke_sensitive_requires_valid_approval(self, registry: ToolRegistry):
        registry.register(_make_tool("secret_tool", sensitive=True))
        raw_input = {"action": "approve"}
        expected_hash = hashlib.sha256(
            json.dumps(raw_input, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()

        approval = CommandReceipt(
            command_id=uuid4(),
            command="secret_tool",
            status="accepted",
            scope="portfolio.write",
            impact_hash=expected_hash,
        )
        result = await registry.invoke(
            "secret_tool",
            raw_input,
            allowlist={"secret_tool"},
            approval=approval,
        )
        assert result == _SensitiveOutput(status="confirmed")

    @pytest.mark.asyncio
    async def test_invoke_sensitive_without_approval_raises(self, registry: ToolRegistry):
        registry.register(_make_tool("secret_tool", sensitive=True))
        with pytest.raises(ToolApprovalRequiredError, match="requires an accepted scoped approval"):
            await registry.invoke(
                "secret_tool",
                {"action": "approve"},
                allowlist={"secret_tool"},
            )

    @pytest.mark.asyncio
    async def test_invoke_sensitive_wrong_status_raises(self, registry: ToolRegistry):
        registry.register(_make_tool("secret_tool", sensitive=True))
        raw_input = {"action": "approve"}
        expected_hash = hashlib.sha256(
            json.dumps(raw_input, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        approval = CommandReceipt(
            command_id=uuid4(),
            command="secret_tool",
            status="rejected",
            scope="portfolio.write",
            impact_hash=expected_hash,
        )
        with pytest.raises(ToolApprovalRequiredError):
            await registry.invoke(
                "secret_tool",
                raw_input,
                allowlist={"secret_tool"},
                approval=approval,
            )

    @pytest.mark.asyncio
    async def test_invoke_sensitive_wrong_hash_raises(self, registry: ToolRegistry):
        registry.register(_make_tool("secret_tool", sensitive=True))
        approval = CommandReceipt(
            command_id=uuid4(),
            command="secret_tool",
            status="accepted",
            scope="portfolio.write",
            impact_hash="0" * 64,
        )
        with pytest.raises(ToolApprovalRequiredError):
            await registry.invoke(
                "secret_tool",
                {"action": "approve"},
                allowlist={"secret_tool"},
                approval=approval,
            )

    @pytest.mark.asyncio
    async def test_invoke_sensitive_empty_scope_raises(self, registry: ToolRegistry):
        registry.register(_make_tool("secret_tool", sensitive=True))
        raw_input = {"action": "approve"}
        expected_hash = hashlib.sha256(
            json.dumps(raw_input, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        approval = CommandReceipt(
            command_id=uuid4(),
            command="secret_tool",
            status="accepted",
            scope="  ",
            impact_hash=expected_hash,
        )
        with pytest.raises(ToolApprovalRequiredError):
            await registry.invoke(
                "secret_tool",
                raw_input,
                allowlist={"secret_tool"},
                approval=approval,
            )


# ---------------------------------------------------------------------------
# Tests: command_receipt()
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestCommandReceipt:
    def test_generates_receipt(self):
        impact = {"portfolio_id": "p1", "action": "rebalance"}
        receipt = command_receipt("rebalance", "portfolio.write", impact)

        assert receipt.status == "awaiting_approval"
        assert receipt.command == "rebalance"
        assert receipt.scope == "portfolio.write"
        assert isinstance(receipt.command_id, type(uuid4()))

        canonical = json.dumps(impact, sort_keys=True, separators=(",", ":"), default=str)
        expected_hash = hashlib.sha256(canonical.encode()).hexdigest()
        assert receipt.impact_hash == expected_hash

    def test_deterministic_hash(self):
        impact = {"a": 1, "b": [2, 3]}
        r1 = command_receipt("cmd", "scope", impact)
        r2 = command_receipt("cmd", "scope", impact)
        assert r1.impact_hash == r2.impact_hash
        assert r1.command_id != r2.command_id
