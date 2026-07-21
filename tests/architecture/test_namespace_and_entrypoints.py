from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def test_local_package_does_not_shadow_openai_agents_sdk() -> None:
    assert not (SRC / "agents").exists(), (
        "src/agents shadows the external 'agents' package used by openai-agents. "
        "Move local code to ia_investing.ai and remove src/agents."
    )

    spec = importlib.util.find_spec("agents")
    assert spec is not None, "openai-agents dependency is not importable"
    assert spec.origin is not None
    resolved = Path(spec.origin).resolve()
    assert "site-packages" in resolved.parts, f"'agents' does not resolve to the installed SDK: {resolved}"


def test_scheduler_uses_temporal_not_in_memory() -> None:
    scheduler = SRC / "apps" / "scheduler" / "main.py"
    assert scheduler.exists()
    text = scheduler.read_text(encoding="utf-8")
    assert "Schedule" in text, "Scheduler must use Temporal Schedules"
    assert "reconcile_schedules" in text, "Scheduler must use reconcile_schedules"
    assert "while True" not in text, "Scheduler must not use in-memory loops"
    assert "asyncio.sleep(60)" not in text, "Scheduler must not use asyncio.sleep(60)"


def test_worker_registers_activities() -> None:
    worker = SRC / "apps" / "worker" / "main.py"
    text = worker.read_text(encoding="utf-8")
    assert "activities=" in text, "Temporal worker must register activities explicitly."
    assert "from workflows" not in text, "Worker must use the canonical ia_investing namespace."
    assert "from database." not in text, "Worker must use canonical settings/platform imports."


def test_api_uses_canonical_namespace_and_security() -> None:
    api_main = SRC / "apps" / "api" / "main.py"
    factory = SRC / "apps" / "api" / "app_factory.py"
    main_text = api_main.read_text(encoding="utf-8").lower()
    factory_text = factory.read_text(encoding="utf-8").lower()
    assert "from database." not in main_text
    assert "from workflows" not in main_text
    assert any(token in factory_text for token in ("oidc", "current_user", "authentication", "auth")), (
        "API application factory must compose authentication globally."
    )


def test_entrypoints_use_canonical_settings() -> None:
    entrypoints = [
        ("API app factory", SRC / "apps" / "api" / "app_factory.py"),
        ("API security", SRC / "apps" / "api" / "security.py"),
        ("API dependencies", SRC / "apps" / "api" / "dependencies.py"),
        ("API health route", SRC / "apps" / "api" / "routes" / "health.py"),
        ("API schedules route", SRC / "apps" / "api" / "routes" / "schedules.py"),
        ("Worker main", SRC / "apps" / "worker" / "main.py"),
        ("Scheduler main", SRC / "apps" / "scheduler" / "main.py"),
        ("Agent runner", SRC / "ia_investing" / "ai" / "_runner.py"),
    ]
    for name, path in entrypoints:
        text = path.read_text(encoding="utf-8")
        has_canonical = "from ia_investing.settings import" in text
        has_legacy = "from database.config import" in text or "from database import" in text
        assert has_canonical, f"{name} ({path}) does not import from canonical ia_investing.settings"
        assert not has_legacy, f"{name} ({path}) imports settings via legacy database.config"


def test_settings_load_with_defaults() -> None:
    from ia_investing.settings import Settings

    settings = Settings(_env_file=None)
    assert settings.database.url == "postgresql+asyncpg://postgres:postgres@localhost:5432/stock_intelligence"
    assert settings.database.pool_size == 10
    assert settings.storage.endpoint == "http://localhost:9000"
    assert settings.temporal.address == "localhost:7233"
    assert settings.temporal.namespace == "default"
    assert settings.ai.provider == "mock"
    assert settings.telemetry.enabled is False
    assert settings.application.environment == "development"
    assert settings.application.log_level == "DEBUG"
    assert settings.worker.capability == "research-agents"
