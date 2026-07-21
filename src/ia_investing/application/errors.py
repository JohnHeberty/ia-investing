class IaInvestingError(Exception):
    code: str = "internal_error"
    detail: str = ""

    def __init__(self, message: str = "", detail: str = "") -> None:
        super().__init__(message)
        self.detail = detail


class BusinessRejection(IaInvestingError):
    code: str = "business_rejection"


class ValidationFailure(IaInvestingError):
    code: str = "validation_failure"


class RetryableInfrastructureError(IaInvestingError):
    code: str = "retryable_infrastructure"


class NonRetryableConfigurationError(IaInvestingError):
    code: str = "non_retryable_configuration"


def temporal_retry_policy_from_error(error: Exception) -> dict:
    if isinstance(error, RetryableInfrastructureError):
        return {
            "maximum_attempts": 5,
            "initial_interval": 5,
            "backoff_coefficient": 2.0,
            "non_retryable_error_types": [],
        }
    if isinstance(error, (BusinessRejection, ValidationFailure, NonRetryableConfigurationError)):
        return {
            "maximum_attempts": 1,
            "non_retryable_error_types": ["*"],
        }
    return {
        "maximum_attempts": 3,
        "initial_interval": 1,
        "backoff_coefficient": 2.0,
    }


def is_retryable(error: Exception) -> bool:
    return isinstance(error, RetryableInfrastructureError)
