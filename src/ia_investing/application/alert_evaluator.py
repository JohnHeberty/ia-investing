"""Automatic alert evaluation engine for policy intelligence."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.policy_intelligence import (
    PolicyAlert as DBPolicyAlert,
)
from database.models.policy_intelligence import (
    PolicyObject,
    PolicyObjectVersion,
    PolicyStageEvent,
)
from ia_investing.domain.policy_alerts import (
    DEFAULT_ALERT_RULES,
    AlertRule,
    AlertSeverity,
    AlertType,
    PolicyAlert,
    is_duplicate,
    should_fire_alert,
)

logger = logging.getLogger(__name__)

_DEFAULT_DEDUP_WINDOW_SECONDS = 3600


def _extract_current_value(rule: AlertRule, context: dict[str, Any]) -> Decimal:
    """Extract the current numeric value from context for rule evaluation."""
    if rule.alert_type == AlertType.PROBABILITY_SHIFT:
        forecasts = context.get("forecasts", [])
        if forecasts:
            return Decimal(str(forecasts[0].get("probability", 0)))
        return Decimal("0")

    if rule.alert_type == AlertType.MATERIAL_IMPACT:
        metadata = context.get("version_metadata", {})
        if isinstance(metadata, dict):
            return Decimal(str(metadata.get("material_impact_score", 0)))
        return Decimal("0")

    if rule.alert_type == AlertType.DEADLINE_APPROACHING:
        deadline = context.get("deadline_days")
        if deadline is not None:
            return Decimal(str(deadline))
        return Decimal("999")

    if rule.alert_type == AlertType.SOURCE_FRESHNESS:
        freshness_hours = context.get("source_freshness_hours")
        if freshness_hours is not None:
            return Decimal(str(freshness_hours))
        return Decimal("0")

    return Decimal("0")


def _extract_previous_value(rule: AlertRule, context: dict[str, Any]) -> Decimal | None:
    """Extract the previous numeric value from context for probability shift comparison."""
    if rule.alert_type == AlertType.PROBABILITY_SHIFT:
        forecasts = context.get("forecasts", [])
        if len(forecasts) >= 2:
            return Decimal(str(forecasts[1].get("probability", 0)))
    return None


class AlertEvaluator:
    """Evaluates alert rules against system state and creates alerts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def evaluate_policy_object(
        self,
        *,
        policy_object_id: UUID,
    ) -> list[DBPolicyAlert]:
        """Evaluate all alert rules for a policy object and fire applicable alerts."""
        policy_obj = await self.session.get(PolicyObject, policy_object_id)
        if policy_obj is None:
            return []

        latest_version = await self._get_latest_version(policy_object_id)
        if latest_version is None:
            return []

        stage_events = await self._get_recent_stage_events(policy_object_id)
        existing_db_alerts = await self._get_existing_alerts(policy_object_id)

        context: dict[str, Any] = {
            "policy_object": policy_obj,
            "latest_version": latest_version,
            "stage_events": stage_events,
            "version_metadata": latest_version.get("metadata_payload", {}),
        }

        existing_domain_alerts = [
            PolicyAlert(
                id=a.id,
                alert_type=AlertType(a.alert_type),
                severity=AlertSeverity(a.severity),
                policy_object_id=a.policy_object_id,
                title=a.title,
                description=a.description or "",
                metadata=a.details or {},
                created_at=a.fired_at,
                resolved=a.resolved_at is not None,
            )
            for a in existing_db_alerts
        ]

        fired_domain: list[PolicyAlert] = []
        fired_db: list[DBPolicyAlert] = []

        for rule in DEFAULT_ALERT_RULES:
            if not rule.enabled:
                continue

            current_value = _extract_current_value(rule, context)
            previous_value = _extract_previous_value(rule, context)

            if not should_fire_alert(rule, current_value=current_value, previous_value=previous_value):
                continue

            now = datetime.now(UTC)
            candidate_domain = PolicyAlert(
                id=uuid4(),
                alert_type=rule.alert_type,
                severity=rule.severity,
                policy_object_id=policy_object_id,
                title=f"{rule.alert_type.value}: {policy_obj.title}",
                description=_generate_description(rule, context),
                metadata={"rule": rule.alert_type.value},
                created_at=now,
            )

            all_existing = existing_domain_alerts + fired_domain
            if is_duplicate(all_existing, candidate_domain, window_seconds=_DEFAULT_DEDUP_WINDOW_SECONDS):
                continue

            db_alert = DBPolicyAlert(
                id=candidate_domain.id,
                policy_object_id=policy_object_id,
                alert_type=rule.alert_type.value,
                severity=rule.severity.value,
                title=candidate_domain.title,
                description=candidate_domain.description,
                details=candidate_domain.metadata,
                fired_at=now,
            )
            self.session.add(db_alert)
            fired_domain.append(candidate_domain)
            fired_db.append(db_alert)
            logger.info(
                "Fired alert %s for policy %s",
                rule.alert_type.value,
                policy_object_id,
            )

        if fired_db:
            await self.session.flush()

        return fired_db

    async def evaluate_all_policies(self) -> list[DBPolicyAlert]:
        """Evaluate alerts for all active policy objects."""
        stmt = sa.select(PolicyObject.id)
        policy_ids = list((await self.session.execute(stmt)).scalars())

        all_alerts: list[DBPolicyAlert] = []
        for policy_id in policy_ids:
            alerts = await self.evaluate_policy_object(policy_object_id=policy_id)
            all_alerts.extend(alerts)

        return all_alerts

    async def _get_latest_version(self, policy_object_id: UUID) -> dict[str, Any] | None:
        stmt = (
            sa.select(PolicyObjectVersion)
            .where(PolicyObjectVersion.policy_object_id == policy_object_id)
            .order_by(PolicyObjectVersion.version.desc())
            .limit(1)
        )
        version = (await self.session.execute(stmt)).scalar_one_or_none()
        if version is None:
            return None
        return {
            "id": version.id,
            "version": version.version,
            "text_content": version.text_content,
            "metadata_payload": version.metadata_payload,
            "published_at": version.published_at,
            "knowledge_at": version.knowledge_at,
        }

    async def _get_recent_stage_events(self, policy_object_id: UUID) -> list[dict[str, Any]]:
        since = datetime.now(UTC) - timedelta(days=30)
        stmt = (
            sa.select(PolicyStageEvent)
            .where(
                PolicyStageEvent.policy_object_id == policy_object_id,
                PolicyStageEvent.knowledge_at >= since,
            )
            .order_by(PolicyStageEvent.knowledge_at.desc())
        )
        events = list((await self.session.execute(stmt)).scalars())
        return [
            {
                "id": e.id,
                "stage": e.stage,
                "occurred_at": e.occurred_at,
                "knowledge_at": e.knowledge_at,
                "metadata_payload": e.metadata_payload,
            }
            for e in events
        ]

    async def _get_existing_alerts(self, policy_object_id: UUID) -> list[DBPolicyAlert]:
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        stmt = (
            sa.select(DBPolicyAlert)
            .where(
                DBPolicyAlert.policy_object_id == policy_object_id,
                DBPolicyAlert.fired_at >= cutoff,
            )
            .order_by(DBPolicyAlert.fired_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars())


def _generate_description(rule: AlertRule, context: dict[str, Any]) -> str:
    """Generate a human-readable description for the alert."""
    policy_obj = context.get("policy_object")
    title = getattr(policy_obj, "title", "unknown")
    return f"{rule.description} — {title}"
