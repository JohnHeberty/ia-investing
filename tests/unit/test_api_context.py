"""Tests for apps.api._context — InstitutionalAccessContext builder."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from apps.api._context import context_from
from apps.api.security import AuthContext


class TestContextFrom:
    def test_builds_context_from_valid_auth(self) -> None:
        org_id = uuid4()
        team_id = uuid4()
        auth = AuthContext(
            subject="user-1",
            permissions=frozenset({"portfolio:read"}),
            authentication_method="oidc",
            organization_id=org_id,
            roles=frozenset({"manager"}),
            team_ids=frozenset({team_id}),
        )
        ctx = context_from(auth)
        assert ctx.subject == "user-1"
        assert ctx.organization_id == org_id
        assert ctx.team_ids == frozenset({team_id})
        assert ctx.permissions == frozenset({"portfolio:read"})
        assert ctx.environment == "paper"

    def test_raises_403_when_no_organization(self) -> None:
        auth = AuthContext(
            subject="user-1",
            permissions=frozenset(),
            authentication_method="oidc",
            organization_id=None,
        )
        with pytest.raises(HTTPException) as exc_info:
            context_from(auth)
        assert exc_info.value.status_code == 403
        assert "institutional organization context is required" in exc_info.value.detail

    def test_empty_permissions(self) -> None:
        org_id = uuid4()
        auth = AuthContext(
            subject="user-2",
            permissions=frozenset(),
            authentication_method="development-header",
            organization_id=org_id,
        )
        ctx = context_from(auth)
        assert ctx.permissions == frozenset()

    def test_empty_team_ids(self) -> None:
        org_id = uuid4()
        auth = AuthContext(
            subject="user-3",
            permissions=frozenset({"agent:run"}),
            authentication_method="oidc",
            organization_id=org_id,
            team_ids=frozenset(),
        )
        ctx = context_from(auth)
        assert ctx.team_ids == frozenset()

    def test_multiple_teams(self) -> None:
        org_id = uuid4()
        t1, t2 = uuid4(), uuid4()
        auth = AuthContext(
            subject="user-4",
            permissions=frozenset(),
            authentication_method="oidc",
            organization_id=org_id,
            team_ids=frozenset({t1, t2}),
        )
        ctx = context_from(auth)
        assert ctx.team_ids == frozenset({t1, t2})
