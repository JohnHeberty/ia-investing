from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from ia_investing.application.security import (
    ActorContext,
    SecurityAuditor,
    get_security_auditor,
)


@pytest.fixture()
def auditor() -> SecurityAuditor:
    return SecurityAuditor()


class TestSecurityAuditor:
    def test_on_auth_failure_logs_warning(self, auditor: SecurityAuditor) -> None:
        with patch("ia_investing.application.security.logger") as mock_logger:
            auditor.on_auth_failure(token_present=True, detail="expired")

            mock_logger.warning.assert_called_once_with(
                "auth_failure",
                token_present=True,
                detail="expired",
            )

    def test_on_auth_failure_no_token(self, auditor: SecurityAuditor) -> None:
        with patch("ia_investing.application.security.logger") as mock_logger:
            auditor.on_auth_failure(token_present=False, detail="missing")

            mock_logger.warning.assert_called_once_with(
                "auth_failure",
                token_present=False,
                detail="missing",
            )

    def test_on_permission_denied_logs_warning(self, auditor: SecurityAuditor) -> None:
        actor = ActorContext(
            subject="user-1",
            organization_id=uuid4(),
            permissions=frozenset({"portfolio:read"}),
        )
        with patch("ia_investing.application.security.logger") as mock_logger:
            auditor.on_permission_denied(actor=actor, resource="portfolio", action="delete", detail="insufficient")

            mock_logger.warning.assert_called_once_with(
                "permission_denied",
                actor_subject="user-1",
                resource="portfolio",
                action="delete",
                detail="insufficient",
            )

    def test_on_permission_denied_none_actor(self, auditor: SecurityAuditor) -> None:
        with patch("ia_investing.application.security.logger") as mock_logger:
            auditor.on_permission_denied(actor=None, resource="x", action="y", detail="z")

            mock_logger.warning.assert_called_once_with(
                "permission_denied",
                actor_subject=None,
                resource="x",
                action="y",
                detail="z",
            )

    def test_on_csrf_failure_logs_warning(self, auditor: SecurityAuditor) -> None:
        with patch("ia_investing.application.security.logger") as mock_logger:
            auditor.on_csrf_failure(ip="10.0.0.1", path="/api/v1/portfolios")

            mock_logger.warning.assert_called_once_with(
                "csrf_failure",
                ip="10.0.0.1",
                path="/api/v1/portfolios",
            )

    def test_on_ssrf_blocked_logs_warning(self, auditor: SecurityAuditor) -> None:
        with patch("ia_investing.application.security.logger") as mock_logger:
            auditor.on_ssrf_blocked(host="evil.com", ip="203.0.113.1")

            mock_logger.warning.assert_called_once_with(
                "ssrf_blocked",
                host="evil.com",
                ip="203.0.113.1",
            )

    def test_on_rate_limit_exceeded_logs_warning(self, auditor: SecurityAuditor) -> None:
        with patch("ia_investing.application.security.logger") as mock_logger:
            auditor.on_rate_limit_exceeded(ip="10.0.0.1", path="/api/v1/data")

            mock_logger.warning.assert_called_once_with(
                "rate_limit_exceeded",
                ip="10.0.0.1",
                path="/api/v1/data",
            )


class TestGetSecurityAuditor:
    def test_returns_singleton(self) -> None:
        import ia_investing.application.security as mod

        original = mod._security_auditor
        mod._security_auditor = None
        try:
            a1 = get_security_auditor()
            a2 = get_security_auditor()
            assert a1 is a2
        finally:
            mod._security_auditor = original
