from __future__ import annotations

from uuid import uuid4

import pytest

from ia_investing.orchestration.activities.candidate_dispatch import (
    _datetime,
    _uuid,
)


class TestUuidParser:
    def test_valid_uuid_string(self) -> None:
        uid = uuid4()
        assert _uuid({"id": str(uid)}, "id") == uid

    def test_raises_on_missing_key(self) -> None:
        with pytest.raises(ValueError, match="invalid or missing"):
            _uuid({}, "id")

    def test_raises_on_invalid_value(self) -> None:
        with pytest.raises(ValueError, match="invalid or missing"):
            _uuid({"id": "not-a-uuid"}, "id")

    def test_raises_on_none_value(self) -> None:
        with pytest.raises(ValueError, match="invalid or missing"):
            _uuid({"id": None}, "id")

    def test_raises_on_none_payload(self) -> None:
        with pytest.raises(ValueError, match="invalid or missing"):
            _uuid(None, "id")  # type: ignore[arg-type]


class TestDatetimeParser:
    def test_valid_iso_datetime(self) -> None:
        result = _datetime({"ts": "2026-01-15T10:30:00+00:00"}, "ts")
        assert result.year == 2026
        assert result.month == 1
        assert result.tzinfo is not None

    def test_z_suffix_becomes_utc(self) -> None:
        result = _datetime({"ts": "2026-06-01T12:00:00Z"}, "ts")
        assert result.tzinfo is not None
        assert result.tzinfo.utcoffset(result) == __import__("datetime").timedelta(0)

    def test_naive_datetime_gets_utc(self) -> None:
        result = _datetime({"ts": "2026-03-10T08:00:00"}, "ts")
        assert result.tzinfo is not None

    def test_raises_on_missing_key(self) -> None:
        with pytest.raises(ValueError, match="invalid or missing"):
            _datetime({}, "ts")

    def test_raises_on_invalid_format(self) -> None:
        with pytest.raises(ValueError, match="invalid or missing"):
            _datetime({"ts": "not-a-date"}, "ts")

    def test_raises_on_none_payload(self) -> None:
        with pytest.raises(ValueError, match="invalid or missing"):
            _datetime(None, "ts")  # type: ignore[arg-type]
