"""Tests for legacy bridge, candidate intelligence events, and audit modules."""

from __future__ import annotations

import sys
import types
import warnings

import pytest

from ia_investing._legacy_bridge import _TRACKED_ACCESS, LegacyBridge, LegacyModuleError
from ia_investing.candidate_intelligence.events import CandidateEvent


# ---------------------------------------------------------------------------
# _legacy_bridge.py
# ---------------------------------------------------------------------------
class TestLegacyBridge:
    def test_getattr_delegates(self):
        mod = types.ModuleType("test_mod")
        mod.foo = "bar"
        bridge = LegacyBridge(mod)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert bridge.foo == "bar"

    def test_getattr_tracks_access(self):
        mod = types.ModuleType("test_mod_tracked")
        mod.x = 1
        bridge = LegacyBridge(mod)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            _ = bridge.x
        assert "x" in _TRACKED_ACCESS.get("test_mod_tracked", [])

    def test_getattr_private_returns_direct(self):
        mod = types.ModuleType("test_priv")
        bridge = LegacyBridge(mod)
        assert bridge._module is mod

    def test_strict_mode_raises(self):
        import ia_investing._legacy_bridge as lb

        old_strict = lb._STRICT
        lb._STRICT = True
        try:
            mod = types.ModuleType("test_strict")
            mod.foo = "bar"
            bridge = LegacyBridge(mod)
            with pytest.raises(LegacyModuleError):
                _ = bridge.foo
        finally:
            lb._STRICT = old_strict

    def test_install(self):
        mod = types.ModuleType("test_install_bridge")
        bridge = LegacyBridge.install(mod)
        assert sys.modules["test_install_bridge"] is bridge
        # cleanup
        sys.modules.pop("test_install_bridge", None)


# ---------------------------------------------------------------------------
# candidate_intelligence/events.py
# ---------------------------------------------------------------------------
class TestCandidateEvent:
    def test_create(self):
        from uuid import uuid4

        event = CandidateEvent.create(
            candidate_id=uuid4(),
            organization_id=uuid4(),
            event_type="created",
            actor_type="system",
            actor_id="auto",
            aggregate_version=1,
        )
        assert event.event_type == "created"
        assert event.payload == {}
        assert event.id is not None

    def test_create_with_payload(self):
        from uuid import uuid4

        event = CandidateEvent.create(
            candidate_id=uuid4(),
            organization_id=uuid4(),
            event_type="updated",
            actor_type="user",
            actor_id="u1",
            aggregate_version=2,
            payload={"key": "value"},
        )
        assert event.payload == {"key": "value"}

    def test_frozen(self):
        from uuid import uuid4

        event = CandidateEvent.create(
            candidate_id=uuid4(),
            organization_id=uuid4(),
            event_type="test",
            actor_type="system",
            actor_id="a",
            aggregate_version=1,
        )
        with pytest.raises(AttributeError):
            event.event_type = "changed"


# ---------------------------------------------------------------------------
# database/models/audit_models.py
# ---------------------------------------------------------------------------
class TestAuditLogModel:
    def test_import(self):
        from database.models.audit_models import AuditLog

        assert AuditLog.__tablename__ == "audit_logs"

    def test_repr(self):
        from database.models.audit_models import AuditLog

        obj = AuditLog()
        obj.actor_type = "user"
        obj.action = "create"
        assert "user" in repr(obj)


# ---------------------------------------------------------------------------
# database/models/audit_listeners.py
# ---------------------------------------------------------------------------
class TestAuditListeners:
    def test_resolve_resource_type(self):
        from database.models.audit_listeners import _resolve_resource_type

        class Portfolio:
            __name__ = "Portfolio"

        assert _resolve_resource_type(Portfolio) == "portfolio"

    def test_resolve_unknown(self):
        from database.models.audit_listeners import _resolve_resource_type

        class SomethingElse:
            __name__ = "SomethingElse"

        assert _resolve_resource_type(SomethingElse) == "somethingelse"

    def test_serialize_value_dict(self):
        from database.models.audit_listeners import _serialize_value

        assert _serialize_value({"a": 1}) == {"a": 1}

    def test_serialize_value_list(self):
        from database.models.audit_listeners import _serialize_value

        assert _serialize_value([1, 2]) == [1, 2]

    def test_serialize_value_isoformat(self):
        from datetime import datetime

        from database.models.audit_listeners import _serialize_value

        dt = datetime(2024, 1, 1)
        assert _serialize_value(dt) == "2024-01-01T00:00:00"

    def test_serialize_value_hex(self):
        from uuid import uuid4

        from database.models.audit_listeners import _serialize_value

        uid = uuid4()
        result = _serialize_value(uid)
        assert isinstance(result, str)

    def test_serialize_value_primitive(self):
        from database.models.audit_listeners import _serialize_value

        assert _serialize_value(42) == 42
        assert _serialize_value("hello") == "hello"

    def test_get_auditable_columns(self):
        from database.models.audit import AuditLogEntry
        from database.models.audit_listeners import _get_auditable_columns

        cols = _get_auditable_columns(AuditLogEntry)
        assert "hash_prev" not in cols
        assert "hash" not in cols
        assert "created_at" not in cols
        assert len(cols) > 0


# ---------------------------------------------------------------------------
# database/models/_utils.py
# ---------------------------------------------------------------------------
class TestUtils:
    def test_utcnow(self):
        from datetime import datetime

        from database.models._utils import utcnow

        result = utcnow()
        assert isinstance(result, datetime)
