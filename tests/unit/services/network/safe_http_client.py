from __future__ import annotations

import pytest

from ia_investing.platform.http.safe_client import (
    EgressPolicy,
    UnsafeUrlError,
    normalize_and_validate_url,
)


def test_rejects_plain_http() -> None:
    with pytest.raises(UnsafeUrlError, match="HTTPS"):
        normalize_and_validate_url("http://example.com/report", EgressPolicy())


def test_rejects_embedded_credentials() -> None:
    with pytest.raises(UnsafeUrlError, match="credentials"):
        normalize_and_validate_url("https://user:secret@example.com/report", EgressPolicy())


@pytest.mark.parametrize(
    "url",
    (
        "https://127.0.0.1/report",
        "https://10.0.0.5/report",
        "https://169.254.169.254/latest/meta-data",
        "https://localhost/report",
        "https://metadata.google.internal/report",
    ),
)
def test_rejects_private_and_metadata_targets(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        normalize_and_validate_url(url, EgressPolicy())


def test_enforces_host_allowlist_and_normalizes_fragment() -> None:
    policy = EgressPolicy(allowed_host_suffixes=("example.com",))
    assert (
        normalize_and_validate_url("https://RI.Example.com/results?q=1#fragment", policy)
        == "https://ri.example.com/results?q=1"
    )
    with pytest.raises(UnsafeUrlError, match="allowlist"):
        normalize_and_validate_url("https://example.net/results", policy)
