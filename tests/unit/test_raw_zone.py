from datetime import UTC, datetime
from uuid import UUID

import pytest

from ia_investing.data.raw_zone import RawObjectInput, build_storage_key, sha256_hex


def test_storage_key_is_content_addressed_and_stable() -> None:
    object_id = UUID("11111111-1111-1111-1111-111111111111")
    digest = sha256_hex(b"official fixture")

    assert digest == "33af8e3c17a9a70df7731b573d72ac43edddd9a122a5b0c5640a8ed57758e2b6"
    assert build_storage_key("CVM", object_id, digest) == f"raw/cvm/{object_id}/{digest}"


def test_storage_key_rejects_non_sha256_values() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        build_storage_key("CVM", UUID(int=0), "not-a-digest")


def test_raw_input_preserves_aware_source_timestamps() -> None:
    item = RawObjectInput(
        source_code="CVM",
        logical_uri="cvm://dfp/2025/example.csv",
        object_type="DFP",
        content=b"fixture",
        media_type="text/csv",
        discovered_at=datetime(2026, 7, 18, tzinfo=UTC),
    )
    assert item.discovered_at.tzinfo is UTC
