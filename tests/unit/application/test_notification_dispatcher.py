"""Unit tests for ia_investing.application.notification_dispatcher."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ia_investing.application.notification_dispatcher import (
    NotificationChannel,
    NotificationDispatcher,
    NotificationMessage,
)


@pytest.fixture()
def message() -> NotificationMessage:
    return NotificationMessage(
        title="Risk Breach",
        body="VaR exceeded threshold",
        severity="CRITICAL",
        alert_type="risk_breach",
        entity_id="port-001",
        entity_type="portfolio",
    )


@pytest.fixture()
def dispatcher_empty() -> NotificationDispatcher:
    return NotificationDispatcher()


class TestDispatch:
    async def test_returns_empty_when_no_channels(
        self, dispatcher_empty: NotificationDispatcher, message: NotificationMessage
    ) -> None:
        results = await dispatcher_empty.dispatch(message)
        assert results == {}

    async def test_dashboard_always_succeeds(self, message: NotificationMessage) -> None:
        dispatcher = NotificationDispatcher(
            channels=[NotificationChannel(type="dashboard", config={})]
        )
        results = await dispatcher.dispatch(message)
        assert results == {"dashboard": True}

    async def test_unknown_channel_returns_false(self, message: NotificationMessage) -> None:
        dispatcher = NotificationDispatcher(
            channels=[NotificationChannel(type="carrier_pigeon", config={})]
        )
        results = await dispatcher.dispatch(message)
        assert results == {"carrier_pigeon": False}

    async def test_multiple_channels(self, message: NotificationMessage) -> None:
        dispatcher = NotificationDispatcher(
            channels=[
                NotificationChannel(type="dashboard", config={}),
                NotificationChannel(type="slack", config={"webhook_url": "https://hook.test"}),
            ]
        )
        with patch.object(
            NotificationDispatcher, "_send_slack", new_callable=AsyncMock, return_value=True
        ):
            results = await dispatcher.dispatch(message)
        assert results["dashboard"] is True
        assert results["slack"] is True

    async def test_channel_exception_returns_false(self, message: NotificationMessage) -> None:
        dispatcher = NotificationDispatcher(
            channels=[NotificationChannel(type="slack", config={"webhook_url": "https://hook.test"})]
        )
        with patch.object(
            NotificationDispatcher, "_send_slack", new_callable=AsyncMock, side_effect=RuntimeError("boom")
        ):
            results = await dispatcher.dispatch(message)
        assert results["slack"] is False


class TestSendSlack:
    async def test_success(self, message: NotificationMessage) -> None:
        dispatcher = NotificationDispatcher()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("ia_investing.application.notification_dispatcher.httpx.AsyncClient", return_value=mock_client):
            result = await dispatcher._send_slack(message, {"webhook_url": "https://hook.test"})

        assert result is True
        mock_client.post.assert_called_once()

    async def test_no_webhook_url(self, message: NotificationMessage) -> None:
        dispatcher = NotificationDispatcher()
        result = await dispatcher._send_slack(message, {})
        assert result is False

    async def test_http_error(self, message: NotificationMessage) -> None:
        dispatcher = NotificationDispatcher()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("ia_investing.application.notification_dispatcher.httpx.AsyncClient", return_value=mock_client):
            result = await dispatcher._send_slack(message, {"webhook_url": "https://hook.test"})

        assert result is False


class TestSendWebhook:
    async def test_success(self, message: NotificationMessage) -> None:
        dispatcher = NotificationDispatcher()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("ia_investing.application.notification_dispatcher.httpx.AsyncClient", return_value=mock_client):
            result = await dispatcher._send_webhook(message, {"url": "https://webhook.test"})

        assert result is True

    async def test_no_url(self, message: NotificationMessage) -> None:
        dispatcher = NotificationDispatcher()
        result = await dispatcher._send_webhook(message, {})
        assert result is False

    async def test_http_error(self, message: NotificationMessage) -> None:
        dispatcher = NotificationDispatcher()
        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("ia_investing.application.notification_dispatcher.httpx.AsyncClient", return_value=mock_client):
            result = await dispatcher._send_webhook(message, {"url": "https://webhook.test"})

        assert result is False


class TestSeverityColor:
    def test_critical(self) -> None:
        dispatcher = NotificationDispatcher()
        assert dispatcher._severity_color("CRITICAL") == "#ff0000"

    def test_warning(self) -> None:
        dispatcher = NotificationDispatcher()
        assert dispatcher._severity_color("WARNING") == "#ffaa00"

    def test_info(self) -> None:
        dispatcher = NotificationDispatcher()
        assert dispatcher._severity_color("INFO") == "#00aa00"

    def test_unknown_severity(self) -> None:
        dispatcher = NotificationDispatcher()
        assert dispatcher._severity_color("debug") == "#888888"
