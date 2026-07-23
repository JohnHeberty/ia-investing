"""Architecture guard tests.

These tests verify structural invariants that prevent regressions
in the project's architecture. They should run on every CI pass.
"""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
PYPROJECT = ROOT / "pyproject.toml"


class TestPackageDiscovery:
    """Verify pyproject.toml package discovery is restricted."""

    def test_package_discovery_not_too_broad(self) -> None:
        with open(PYPROJECT, "rb") as f:
            cfg = tomllib.load(f)
        include = cfg["tool"]["setuptools"]["packages"]["find"]["include"]
        assert include != ["*"], f"Package discovery too broad: {include}"
        assert "ia_investing*" in include, "ia_investing* not in include"
        assert "apps*" in include, "apps* not in include"

    def test_agents_package_not_in_include(self) -> None:
        with open(PYPROJECT, "rb") as f:
            cfg = tomllib.load(f)
        include = cfg["tool"]["setuptools"]["packages"]["find"]["include"]
        for pattern in include:
            assert "agents" not in pattern.lower() or pattern == "ia_investing*", (
                f"Legacy 'agents' package in discovery: {pattern}"
            )


class TestNoSrcAgents:
    """Verify src/agents directory is removed to prevent shadowing openai-agents."""

    def test_src_agents_removed(self) -> None:
        agents_dir = SRC / "agents"
        assert not agents_dir.exists(), (
            f"src/agents/ still exists and would shadow the openai-agents package. Remove it: rm -rf {agents_dir}"
        )

    def test_agents_module_resolves_to_installed_package(self) -> None:
        mod = importlib.import_module("agents")
        mod_file = getattr(mod, "__file__", "") or ""
        assert mod_file, "agents module has no __file__"
        assert "src/agents" not in mod_file, (
            f"agents module resolves to local src/agents ({mod_file}), not the installed openai-agents package"
        )


class TestEntryPointsHaveActivities:
    """Verify Temporal worker registers activities alongside workflows."""

    def test_worker_imports_activities(self) -> None:
        worker_main = SRC / "apps" / "worker" / "main.py"
        content = worker_main.read_text(encoding="utf-8")
        assert "ACTIVITIES_BY_CAPABILITY" in content, "Worker does not define ACTIVITIES_BY_CAPABILITY"
        assert "activities=activities" in content, "Worker does not pass activities to Worker()"

    def test_api_mounts_all_routers(self) -> None:
        candidates = [
            SRC / "apps" / "api" / "main.py",
            SRC / "apps" / "api" / "app_factory.py",
        ]
        content = ""
        for path in candidates:
            if path.exists():
                content += path.read_text(encoding="utf-8")
        required_routers = [
            "health",
            "paper_execution",
            "readiness",
            "policy",
            "research",
            "agents",
        ]
        for router in required_routers:
            assert (
                f"include_router({router}" in content
                or f"include_router({router}_router" in content
                or f"from .routes.{router} import" in content
                or f"from apps.api.routes.{router} import" in content
            ), f"API does not mount {router} router"


class TestSchedulerUsesTemporal:
    """Verify scheduler uses Temporal Schedules, not in-memory loops."""

    def test_no_infinite_loop(self) -> None:
        scheduler_main = SRC / "apps" / "scheduler" / "main.py"
        content = scheduler_main.read_text(encoding="utf-8")
        assert "while True" not in content, "Scheduler uses in-memory while True loop"
        assert "asyncio.sleep(60)" not in content, "Scheduler uses asyncio.sleep(60) loop"

    def test_uses_temporal_schedules(self) -> None:
        scheduler_dir = SRC / "apps" / "scheduler"
        content = ""
        for path in [scheduler_dir / "main.py", scheduler_dir / "temporal_schedules.py"]:
            if path.exists():
                content += path.read_text(encoding="utf-8")
        assert "Schedule" in content, "Scheduler does not use Temporal Schedules"


class TestSecurityInfrastructure:
    """Verify security infrastructure exists and is properly structured."""

    def test_security_module_exists(self) -> None:
        security_file = SRC / "apps" / "api" / "security.py"
        assert security_file.exists(), "security.py does not exist"

    def test_oidc_decode_function(self) -> None:
        security_file = SRC / "apps" / "api" / "security.py"
        content = security_file.read_text(encoding="utf-8")
        assert "_decode_oidc_token" in content, "No OIDC token decoding function"
        assert "get_auth_context" in content, "No get_auth_context dependency"

    def test_auth_required_on_paper_routes(self) -> None:
        paper_routes = SRC / "apps" / "api" / "routes" / "paper_execution.py"
        content = paper_routes.read_text(encoding="utf-8")
        assert "get_auth_context" in content, "Paper execution routes do not require authentication"
