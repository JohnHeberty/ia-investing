from __future__ import annotations

import pytest
from fastapi import HTTPException

from apps.api.security import AuthContext, get_auth_context, require_permission
from ia_investing.settings import get_settings


@pytest.mark.asyncio
async def test_development_identity_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPLICATION__ENVIRONMENT", "development")
    get_settings.cache_clear()
    try:
        context = await get_auth_context(
            credentials=None,
            dev_subject="developer@example.com",
            dev_permissions="agent_runs:create operations:read",
            dev_organization=None,
            dev_teams="",
        )
    finally:
        get_settings.cache_clear()

    assert context.subject == "developer@example.com"
    assert context.authentication_method == "development-header"


@pytest.mark.asyncio
async def test_permission_dependency_denies_missing_permission() -> None:
    dependency = require_permission("agent_runs:create")
    context = AuthContext("subject", frozenset(), "test")

    with pytest.raises(HTTPException) as exc_info:
        await dependency(context)

    assert exc_info.value.status_code == 403
