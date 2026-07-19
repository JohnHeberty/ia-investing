from datetime import timedelta

from temporalio.common import RetryPolicy

DEFAULT_ACTIVITY_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=5,
    non_retryable_error_types=["DataValidationError", "ConfigurationError"],
)

EXTERNAL_IO_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=2),
    maximum_attempts=6,
    non_retryable_error_types=["DataValidationError", "LicensePolicyError", "ConfigurationError"],
)
