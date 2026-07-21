from ia_investing.application.errors import BusinessRejection, RetryableInfrastructureError


class AiProviderError(RetryableInfrastructureError):
    code: str = "ai_provider"


class GuardrailViolation(BusinessRejection):
    code: str = "guardrail_violation"


__all__ = [
    "AiProviderError",
    "BusinessRejection",
    "GuardrailViolation",
    "RetryableInfrastructureError",
]
