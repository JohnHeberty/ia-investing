from __future__ import annotations

from pathlib import Path

from apps.api.main import app


def test_api_has_no_live_order_surface_or_broker_dependency() -> None:
    paths = {path.lower() for path in app.openapi()["paths"]}
    forbidden_fragments = ("send-order", "broker-order", "live-order", "fix-order")
    assert not any(fragment in path for path in paths for fragment in forbidden_fragments)
    dependencies = (Path(__file__).parents[2] / "pyproject.toml").read_text(encoding="utf-8").lower()
    forbidden_sdks = ("ib_insync", "interactive-brokers", "metatrader", "quickfix", "alpaca-trade-api")
    assert not any(sdk in dependencies for sdk in forbidden_sdks)
    configuration = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (Path(__file__).parents[2] / ".env.example", Path(__file__).parents[2] / "docker-compose.yml")
    ).lower()
    forbidden_configuration = ("broker_api_key", "broker_secret", "trading_password", "fix_password")
    assert not any(setting in configuration for setting in forbidden_configuration)


def test_paper_resources_are_explicitly_named() -> None:
    paper_paths = [path for path in app.openapi()["paths"] if path.startswith("/api/v1/paper/")]
    assert paper_paths
    assert all("paper" in path for path in paper_paths)
