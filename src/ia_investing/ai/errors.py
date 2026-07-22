from ia_investing.application.errors import BusinessRejectionError, RetryableInfrastructureError


class AiProviderError(RetryableInfrastructureError):
    code: str = "ai_provider"


class GuardrailViolationError(BusinessRejectionError):
    code: str = "guardrail_violation"


__all__ = [
    "AiProviderError",
    "BusinessRejectionError",
    "GuardrailViolationError",
    "RetryableInfrastructureError",
]
