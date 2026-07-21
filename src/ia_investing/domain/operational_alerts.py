"""Operational alert catalog for paper/institutional execution.

Defines alert types, notification channels, escalation rules, and SLA
policies for the paper execution operational alert system. This module
bridges the domain catalog with the OperationalAlert database model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum


class OperationalAlertType(StrEnum):
    RECONCILIATION_BREAK = "reconciliation_break"
    ORDER_REJECTED = "order_rejected"
    ORDER_EXPIRED = "order_expired"
    EXECUTION_DELAY = "execution_delay"
    SLIPPAGE_THRESHOLD = "slippage_threshold"
    COST_THRESHOLD = "cost_threshold"
    RISK_BREACH = "risk_breach"
    SCHEDULE_DELAY = "schedule_delay"
    SOURCE_FRESHNESS = "source_freshness"
    KILL_SWITCH_ACTIVATED = "kill_switch_activated"
    FATAL_ERROR = "fatal_error"


class NotificationChannel(StrEnum):
    DASHBOARD = "dashboard"
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"


class EscalationAction(StrEnum):
    NOTIFY = "notify"
    AUTO_RESOLVE = "auto_resolve"
    BLOCK_OPERATIONS = "block_operations"
    PAGE_ONCALL = "page_oncall"


@dataclass(frozen=True, slots=True)
class AlertTypeDefinition:
    alert_type: OperationalAlertType
    description: str
    default_severity: str
    channels: tuple[NotificationChannel, ...]
    escalation: tuple[EscalationRule, ...]
    auto_resolve_after: timedelta | None = None


@dataclass(frozen=True, slots=True)
class EscalationRule:
    level: int
    delay: timedelta
    action: EscalationAction
    channels: tuple[NotificationChannel, ...]
    description: str


def _make_reconciliation_escalation() -> tuple[EscalationRule, ...]:
    return (
        EscalationRule(
            level=1,
            delay=timedelta(minutes=0),
            action=EscalationAction.NOTIFY,
            channels=(NotificationChannel.DASHBOARD,),
            description="Immediate dashboard notification",
        ),
        EscalationRule(
            level=2,
            delay=timedelta(minutes=30),
            action=EscalationAction.PAGE_ONCALL,
            channels=(NotificationChannel.EMAIL, NotificationChannel.SLACK),
            description="Page on-call after 30 minutes if not acknowledged",
        ),
        EscalationRule(
            level=3,
            delay=timedelta(hours=2),
            action=EscalationAction.BLOCK_OPERATIONS,
            channels=(NotificationChannel.EMAIL, NotificationChannel.SLACK, NotificationChannel.WEBHOOK),
            description="Block operations after 2 hours if unresolved",
        ),
    )


def _make_critical_escalation() -> tuple[EscalationRule, ...]:
    return (
        EscalationRule(
            level=1,
            delay=timedelta(minutes=0),
            action=EscalationAction.NOTIFY,
            channels=(NotificationChannel.DASHBOARD, NotificationChannel.SLACK),
            description="Immediate dashboard + Slack notification",
        ),
        EscalationRule(
            level=2,
            delay=timedelta(minutes=15),
            action=EscalationAction.PAGE_ONCALL,
            channels=(NotificationChannel.EMAIL, NotificationChannel.SLACK),
            description="Page on-call after 15 minutes",
        ),
        EscalationRule(
            level=3,
            delay=timedelta(hours=1),
            action=EscalationAction.BLOCK_OPERATIONS,
            channels=(NotificationChannel.EMAIL, NotificationChannel.SLACK, NotificationChannel.WEBHOOK),
            description="Block operations after 1 hour if unresolved",
        ),
    )


def _make_warning_escalation() -> tuple[EscalationRule, ...]:
    return (
        EscalationRule(
            level=1,
            delay=timedelta(minutes=0),
            action=EscalationAction.NOTIFY,
            channels=(NotificationChannel.DASHBOARD,),
            description="Immediate dashboard notification",
        ),
        EscalationRule(
            level=2,
            delay=timedelta(hours=4),
            action=EscalationAction.NOTIFY,
            channels=(NotificationChannel.EMAIL,),
            description="Email after 4 hours if not acknowledged",
        ),
    )


def _make_info_escalation() -> tuple[EscalationRule, ...]:
    return (
        EscalationRule(
            level=1,
            delay=timedelta(minutes=0),
            action=EscalationAction.NOTIFY,
            channels=(NotificationChannel.DASHBOARD,),
            description="Dashboard only",
        ),
    )


OPERATIONAL_ALERT_CATALOG: dict[OperationalAlertType, AlertTypeDefinition] = {
    OperationalAlertType.RECONCILIATION_BREAK: AlertTypeDefinition(
        alert_type=OperationalAlertType.RECONCILIATION_BREAK,
        description="Portfolio reconciliation detected a break between expected and actual state",
        default_severity="warning",
        channels=(NotificationChannel.DASHBOARD,),
        escalation=_make_reconciliation_escalation(),
    ),
    OperationalAlertType.ORDER_REJECTED: AlertTypeDefinition(
        alert_type=OperationalAlertType.ORDER_REJECTED,
        description="Paper order was rejected by the execution model",
        default_severity="warning",
        channels=(NotificationChannel.DASHBOARD,),
        escalation=_make_warning_escalation(),
    ),
    OperationalAlertType.ORDER_EXPIRED: AlertTypeDefinition(
        alert_type=OperationalAlertType.ORDER_EXPIRED,
        description="Paper order expired without reaching the fill threshold",
        default_severity="info",
        channels=(NotificationChannel.DASHBOARD,),
        escalation=_make_info_escalation(),
    ),
    OperationalAlertType.EXECUTION_DELAY: AlertTypeDefinition(
        alert_type=OperationalAlertType.EXECUTION_DELAY,
        description="Order execution exceeded expected latency threshold",
        default_severity="warning",
        channels=(NotificationChannel.DASHBOARD,),
        escalation=_make_warning_escalation(),
    ),
    OperationalAlertType.SLIPPAGE_THRESHOLD: AlertTypeDefinition(
        alert_type=OperationalAlertType.SLIPPAGE_THRESHOLD,
        description="Fill slippage exceeded configured threshold in basis points",
        default_severity="warning",
        channels=(NotificationChannel.DASHBOARD,),
        escalation=_make_warning_escalation(),
    ),
    OperationalAlertType.COST_THRESHOLD: AlertTypeDefinition(
        alert_type=OperationalAlertType.COST_THRESHOLD,
        description="Total execution costs (fees + taxes) exceeded threshold",
        default_severity="info",
        channels=(NotificationChannel.DASHBOARD,),
        escalation=_make_info_escalation(),
    ),
    OperationalAlertType.RISK_BREACH: AlertTypeDefinition(
        alert_type=OperationalAlertType.RISK_BREACH,
        description="Portfolio risk metrics breached policy limits",
        default_severity="critical",
        channels=(NotificationChannel.DASHBOARD, NotificationChannel.SLACK),
        escalation=_make_critical_escalation(),
    ),
    OperationalAlertType.SCHEDULE_DELAY: AlertTypeDefinition(
        alert_type=OperationalAlertType.SCHEDULE_DELAY,
        description="Scheduled operation (rebalance, valuation) missed its window",
        default_severity="warning",
        channels=(NotificationChannel.DASHBOARD,),
        escalation=_make_warning_escalation(),
    ),
    OperationalAlertType.SOURCE_FRESHNESS: AlertTypeDefinition(
        alert_type=OperationalAlertType.SOURCE_FRESHNESS,
        description="Market data source freshness exceeded staleness threshold",
        default_severity="warning",
        channels=(NotificationChannel.DASHBOARD,),
        escalation=_make_warning_escalation(),
    ),
    OperationalAlertType.KILL_SWITCH_ACTIVATED: AlertTypeDefinition(
        alert_type=OperationalAlertType.KILL_SWITCH_ACTIVATED,
        description="Kill switch was activated, blocking paper operations",
        default_severity="critical",
        channels=(NotificationChannel.DASHBOARD, NotificationChannel.SLACK, NotificationChannel.EMAIL),
        escalation=_make_critical_escalation(),
    ),
    OperationalAlertType.FATAL_ERROR: AlertTypeDefinition(
        alert_type=OperationalAlertType.FATAL_ERROR,
        description="Fatal error in paper execution pipeline",
        default_severity="critical",
        channels=(NotificationChannel.DASHBOARD, NotificationChannel.SLACK, NotificationChannel.EMAIL),
        escalation=_make_critical_escalation(),
    ),
}


def get_alert_definition(alert_type: OperationalAlertType) -> AlertTypeDefinition:
    return OPERATIONAL_ALERT_CATALOG[alert_type]


def make_deduplication_key(
    alert_type: OperationalAlertType,
    portfolio_id: str,
    resource_key: str,
    date_str: str,
) -> str:
    return f"{alert_type.value}:{portfolio_id}:{date_str}:{resource_key}"


def evaluate_escalation_level(
    definition: AlertTypeDefinition,
    *,
    elapsed: timedelta,
    acknowledged: bool,
) -> EscalationRule | None:
    if acknowledged:
        return None
    current: EscalationRule | None = None
    for rule in definition.escalation:
        if elapsed >= rule.delay:
            current = rule
    return current
