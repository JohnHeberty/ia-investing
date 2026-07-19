from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def test_local_agent_runtime_has_non_colliding_namespace() -> None:
    spec = importlib.util.find_spec("ia_investing.ai")
    assert spec is not None
    assert spec.origin is not None
    assert Path(spec.origin).as_posix().endswith("ia_investing/ai/__init__.py")


def test_no_local_top_level_agents_package() -> None:
    local_agents = Path(__file__).parents[2] / "src" / "agents"
    assert not (local_agents / "__init__.py").exists()


def test_openai_agents_sdk_imports_when_dependencies_are_installed() -> None:
    sdk = pytest.importorskip("agents", reason="openai-agents is not installed in the current interpreter")
    if not hasattr(sdk, "Agent"):
        pytest.skip("only a stale local namespace directory exists; the SDK is not installed")
    assert sdk.Agent.__module__.startswith("agents")
    assert sdk.Runner.__module__.startswith("agents")
