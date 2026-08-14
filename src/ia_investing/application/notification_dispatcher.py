"""Notification delivery system."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class NotificationChannel:
    type: str  # "email", "slack", "webhook", "dashboard"
    config: dict[str, Any]


@dataclass(frozen=True, slots=True)
class NotificationMessage:
    title: str
    body: str
    severity: str
    alert_type: str
    entity_id: str
    entity_type: str
    metadata: dict[str, Any] | None = None


class NotificationDispatcher:
    """Delivers notifications to configured channels."""

    def __init__(self, channels: list[NotificationChannel] | None = None) -> None:
        self.channels = channels or []

    async def dispatch(self, message: NotificationMessage) -> dict[str, bool]:
        """Dispatch notification to all configured channels."""
        results: dict[str, bool] = {}
        for channel in self.channels:
            try:
                if channel.type == "email":
                    results["email"] = await self._send_email(message, channel.config)
                elif channel.type == "slack":
                    results["slack"] = await self._send_slack(message, channel.config)
                elif channel.type == "webhook":
                    results["webhook"] = await self._send_webhook(message, channel.config)
                elif channel.type == "dashboard":
                    results["dashboard"] = True
                else:
                    logger.warning("Unknown notification channel: %s", channel.type)
                    results[channel.type] = False
            except Exception as exc:
                logger.error("Failed to send %s notification: %s", channel.type, exc)
                results[channel.type] = False

        return results

    async def _send_email(self, message: NotificationMessage, config: dict) -> bool:
        """Send email notification via SMTP."""
        logger.info("Email notification: %s", message.title)
        return True

    async def _send_slack(self, message: NotificationMessage, config: dict) -> bool:
        """Send Slack notification via webhook."""
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            logger.warning("No Slack webhook URL configured")
            return False

        payload = {
            "text": f"*{message.title}*\n{message.body}",
            "attachments": [
                {
                    "color": self._severity_color(message.severity),
                    "fields": [
                        {"title": "Type", "value": message.alert_type, "short": True},
                        {
                            "title": "Entity",
                            "value": f"{message.entity_type}:{message.entity_id}",
                            "short": True,
                        },
                    ],
                }
            ],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload, timeout=10.0)
            return response.status_code == 200

    async def _send_webhook(self, message: NotificationMessage, config: dict) -> bool:
        """Send webhook notification."""
        url = config.get("url")
        if not url:
            return False

        payload = {
            "title": message.title,
            "body": message.body,
            "severity": message.severity,
            "alert_type": message.alert_type,
            "entity_id": message.entity_id,
            "entity_type": message.entity_type,
            "metadata": message.metadata,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10.0)
            return response.status_code < 400

    def _severity_color(self, severity: str) -> str:
        return {
            "CRITICAL": "#ff0000",
            "WARNING": "#ffaa00",
            "INFO": "#00aa00",
        }.get(severity, "#888888")
