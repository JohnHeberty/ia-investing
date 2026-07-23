from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.orm import Session

from database.models.audit import AuditLogEntry

_AUDITABLE_MODELS: dict[str, type] = {}


def register_auditable(model: type, resource_type: str) -> None:
    _AUDITABLE_MODELS[model.__name__] = model

    @event.listens_for(model, "after_insert")
    def _after_insert(mapper: Any, connection: Any, target: Any) -> None:
        _log_auto(mapper, connection, target, "create")

    @event.listens_for(model, "after_update")
    def _after_update(mapper: Any, connection: Any, target: Any) -> None:
        _log_auto(mapper, connection, target, "update")

    @event.listens_for(model, "after_delete")
    def _after_delete(mapper: Any, connection: Any, target: Any) -> None:
        _log_auto(mapper, connection, target, "delete")


def _log_auto(mapper: Any, connection: Any, target: Any, action: str) -> None:
    session = Session.object_session(target)
    if session is None:
        return

    audit_info = session.info.get("audit")
    if audit_info is None:
        return

    tenant_id = audit_info.get("tenant_id")
    actor_id = audit_info.get("actor_id")
    metadata = audit_info.get("metadata", {})

    if tenant_id is None:
        return

    resource_type = _resolve_resource_type(type(target))
    resource_id = getattr(target, "id", None)

    changes = None
    if action == "update":
        changes = _compute_diff(target)

    prev_hash = _get_latest_hash(connection, tenant_id)
    now = datetime.now(UTC)
    raw = (
        str(prev_hash or "")
        + now.isoformat()
        + str(actor_id or "")
        + action
        + resource_type
        + str(resource_id or "")
        + json.dumps(changes or {}, sort_keys=True)
        + json.dumps(metadata or {}, sort_keys=True)
    )
    entry_hash = sha256(raw.encode("utf-8")).hexdigest()

    connection.execute(
        sa.insert(AuditLogEntry).values(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            changes=changes,
            metadata=metadata,
            hash_prev=prev_hash,
            hash=entry_hash,
            timestamp=now,
            created_at=now,
        )
    )


def _resolve_resource_type(model_type: type) -> str:
    registry = {
        "Portfolio": "portfolio",
        "Transaction": "order",
        "PaperOrder": "order",
        "ResearchThesis": "thesis",
        "AgentRuntimeRun": "agent_run",
        "Operation": "settings",
    }
    return registry.get(model_type.__name__, model_type.__name__.lower())


def _compute_diff(target: Any) -> dict[str, Any] | None:
    session = Session.object_session(target)
    if session is None:
        return None

    from sqlalchemy.orm.attributes import get_history

    changes: dict[str, dict[str, object]] = {}
    for attr_name in _get_auditable_columns(type(target)):
        hist = get_history(target, attr_name)
        if hist.has_changes():
            old_value = _serialize_value(hist.deleted[0]) if hist.deleted else None
            new_value = _serialize_value(hist.added[0]) if hist.added else None
            if old_value is not None or new_value is not None:
                changes[attr_name] = {"before": old_value, "after": new_value}

    return changes if changes else None


def _get_auditable_columns(model_type: type) -> list[str]:
    skip = {"hash_prev", "hash", "timestamp", "created_at", "updated_at"}
    return [c.name for c in model_type.__table__.columns if c.name not in skip]  # type: ignore[attr-defined]


def _serialize_value(value: Any) -> object:
    if isinstance(value, dict | list):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "hex"):
        return str(value)
    return value


def _get_latest_hash(connection: Any, tenant_id: Any) -> str | None:
    result = connection.execute(
        sa.select(AuditLogEntry.hash)
        .where(AuditLogEntry.tenant_id == tenant_id)
        .order_by(AuditLogEntry.timestamp.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row  # type: ignore[no-any-return]
