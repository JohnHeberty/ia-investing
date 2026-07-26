from __future__ import annotations


class ProviderError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = False, safe_detail: str) -> None:
        super().__init__(safe_detail)
        self.code = code
        self.retryable = retryable
        self.safe_detail = safe_detail


class ProviderTimeoutError(ProviderError):
    def __init__(self, message: str = "Provider request timed out", *, safe_detail: str | None = None) -> None:
        super().__init__("provider_timeout", retryable=True, safe_detail=safe_detail or message)


class ProviderRateLimitError(ProviderError):
    def __init__(self, message: str = "Rate limit exceeded", *, safe_detail: str | None = None) -> None:
        super().__init__("provider_rate_limit", retryable=True, safe_detail=safe_detail or message)


class ProviderAuthError(ProviderError):
    def __init__(self, message: str = "Provider authentication failed", *, safe_detail: str | None = None) -> None:
        super().__init__("provider_auth_error", retryable=False, safe_detail=safe_detail or "Authentication failed")


class ProviderBadRequestError(ProviderError):
    def __init__(self, message: str = "Bad request", *, safe_detail: str | None = None) -> None:
        super().__init__("provider_bad_request", retryable=False, safe_detail=safe_detail or "Bad request")
