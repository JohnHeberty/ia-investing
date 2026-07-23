from pathlib import Path

import yaml


def test_override_paths_are_relative_to_repository_root():
    root = Path(__file__).resolve().parents[2]
    compose = yaml.safe_load((root / "infra/compose/docker-compose.refactor.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert services["api"]["build"]["context"] == "."
    assert services["web"]["build"]["context"] == "./web"
    assert services["api"]["env_file"] == [".env"]


def test_backend_image_uses_lockfile():
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY pyproject.toml uv.lock README.md" in dockerfile
    assert "uv sync --frozen" in dockerfile
