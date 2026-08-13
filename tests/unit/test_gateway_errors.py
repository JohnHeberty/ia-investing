"""Unit tests for ia_investing.ai.gateway_errors — Provider error hierarchy."""

from __future__ import annotations

import pytest

from ia_investing.ai.gateway_errors import (
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)


@pytest.mark.unit
class TestProviderError:
    def test_base_error(self):
        err = ProviderError("test_code", retryable=True, safe_detail="detail here")
        assert err.code == "test_code"
        assert err.retryable is True
        assert err.safe_detail == "detail here"
        assert str(err) == "detail here"
        assert isinstance(err, RuntimeError)

    def test_non_retryable(self):
        err = ProviderError("code", retryable=False, safe_detail="x")
        assert err.retryable is False


@pytest.mark.unit
class TestProviderTimeoutError:
    def test_default_message(self):
        err = ProviderTimeoutError()
        assert err.code == "provider_timeout"
        assert err.retryable is True
        assert "timed out" in err.safe_detail

    def test_custom_message(self):
        err = ProviderTimeoutError("custom timeout", safe_detail="custom detail")
        assert err.safe_detail == "custom detail"


@pytest.mark.unit
class TestProviderRateLimitError:
    def test_default(self):
        err = ProviderRateLimitError()
        assert err.code == "provider_rate_limit"
        assert err.retryable is True

    def test_custom(self):
        err = ProviderRateLimitError("rate limited", safe_detail="wait 60s")
        assert err.safe_detail == "wait 60s"


@pytest.mark.unit
class TestProviderAuthError:
    def test_default(self):
        err = ProviderAuthError()
        assert err.code == "provider_auth_error"
        assert err.retryable is False
        assert "Authentication failed" in err.safe_detail


@pytest.mark.unit
class TestProviderBadRequestError:
    def test_default(self):
        err = ProviderBadRequestError()
        assert err.code == "provider_bad_request"
        assert err.retryable is False

    def test_custom(self):
        err = ProviderBadRequestError("invalid input", safe_detail="bad request")
        assert err.safe_detail == "bad request"
