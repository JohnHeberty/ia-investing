from __future__ import annotations

import pytest
from pydantic import ValidationError

from ia_investing.settings import Settings


def test_nested_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPLICATION__ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE__POOL_SIZE", "3")

    settings = Settings(_env_file=None)

    assert settings.application.environment == "test"
    assert settings.database.pool_size == 3


def test_production_rejects_missing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPLICATION__ENVIRONMENT", "production")

    with pytest.raises(ValidationError, match="production configuration"):
        Settings(_env_file=None)


def test_secrets_are_not_exposed_by_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE__ACCESS_KEY", "sensitive-value")

    settings = Settings(_env_file=None)

    assert "sensitive-value" not in repr(settings)
