import pytest

from ia_investing.application.errors import (
    BusinessRejectionError,
    IaInvestingError,
    NonRetryableConfigurationError,
    RetryableInfrastructureError,
    ValidationError,
    is_retryable,
    temporal_retry_policy_from_error,
)
from ia_investing.ai.errors import AiProviderError, GuardrailViolationError


class TestInstantiation:
    def test_base_error_with_message_and_detail(self) -> None:
        err = IaInvestingError("something went wrong", detail="trace_id=abc")
        assert str(err) == "something went wrong"
        assert err.detail == "trace_id=abc"
        assert err.code == "internal_error"

    def test_business_rejection(self) -> None:
        err = BusinessRejectionError("order exceeds limit", detail="limit=10000")
        assert str(err) == "order exceeds limit"
        assert err.detail == "limit=10000"
        assert err.code == "business_rejection"

    def test_validation_failure(self) -> None:
        err = ValidationError("invalid cnpj", detail="cnpj=00.000.000/0001-00")
        assert str(err) == "invalid cnpj"
        assert err.detail == "cnpj=00.000.000/0001-00"
        assert err.code == "validation_failure"

    def test_retryable_infrastructure_error(self) -> None:
        err = RetryableInfrastructureError("timeout", detail="provider=openai")
        assert str(err) == "timeout"
        assert err.detail == "provider=openai"
        assert err.code == "retryable_infrastructure"

    def test_non_retryable_configuration_error(self) -> None:
        err = NonRetryableConfigurationError("missing api key", detail="key=OPENAI_API_KEY")
        assert str(err) == "missing api key"
        assert err.detail == "key=OPENAI_API_KEY"
        assert err.code == "non_retryable_configuration"


class TestIsRetryable:
    def test_retryable_infrastructure_is_retryable(self) -> None:
        assert is_retryable(RetryableInfrastructureError("timeout")) is True

    def test_business_rejection_is_not_retryable(self) -> None:
        assert is_retryable(BusinessRejectionError("rejected")) is False

    def test_validation_failure_is_not_retryable(self) -> None:
        assert is_retryable(ValidationError("invalid")) is False

    def test_non_retryable_configuration_is_not_retryable(self) -> None:
        assert is_retryable(NonRetryableConfigurationError("bad config")) is False

    def test_base_error_is_not_retryable(self) -> None:
        assert is_retryable(IaInvestingError("generic")) is False

    def test_standard_exception_is_not_retryable(self) -> None:
        assert is_retryable(ValueError("nope")) is False


class TestTemporalRetryPolicy:
    def test_retryable_infrastructure_policy(self) -> None:
        policy = temporal_retry_policy_from_error(RetryableInfrastructureError("timeout"))
        assert policy["maximum_attempts"] == 5
        assert policy["initial_interval"] == 5
        assert policy["backoff_coefficient"] == 2.0
        assert policy["non_retryable_error_types"] == []

    def test_business_rejection_policy(self) -> None:
        policy = temporal_retry_policy_from_error(BusinessRejectionError("rejected"))
        assert policy["maximum_attempts"] == 1
        assert policy["non_retryable_error_types"] == ["*"]

    def test_validation_failure_policy(self) -> None:
        policy = temporal_retry_policy_from_error(ValidationError("invalid"))
        assert policy["maximum_attempts"] == 1
        assert policy["non_retryable_error_types"] == ["*"]

    def test_non_retryable_configuration_policy(self) -> None:
        policy = temporal_retry_policy_from_error(NonRetryableConfigurationError("bad"))
        assert policy["maximum_attempts"] == 1
        assert policy["non_retryable_error_types"] == ["*"]

    def test_unknown_exception_default_policy(self) -> None:
        policy = temporal_retry_policy_from_error(RuntimeError("unexpected"))
        assert policy["maximum_attempts"] == 3
        assert policy["initial_interval"] == 1
        assert policy["backoff_coefficient"] == 2.0

    def test_base_error_default_policy(self) -> None:
        policy = temporal_retry_policy_from_error(IaInvestingError("generic"))
        assert policy["maximum_attempts"] == 3


class TestAiErrors:
    def test_ai_provider_error_is_retryable_infrastructure(self) -> None:
        err = AiProviderError("openai timeout", detail="model=gpt-4")
        assert isinstance(err, RetryableInfrastructureError)
        assert err.code == "ai_provider"
        assert str(err) == "openai timeout"
        assert err.detail == "model=gpt-4"

    def test_guardrail_violation_is_business_rejection(self) -> None:
        err = GuardrailViolationError("harmful content detected", detail="category=toxic")
        assert isinstance(err, BusinessRejectionError)
        assert err.code == "guardrail_violation"
        assert str(err) == "harmful content detected"
        assert err.detail == "category=toxic"

    def test_ai_provider_error_retryable(self) -> None:
        assert is_retryable(AiProviderError("timeout")) is True

    def test_guardrail_violation_not_retryable(self) -> None:
        assert is_retryable(GuardrailViolationError("blocked")) is False


class TestHierarchyDepth:
    def test_ai_provider_deep_hierarchy(self) -> None:
        assert issubclass(AiProviderError, RetryableInfrastructureError)
        assert issubclass(RetryableInfrastructureError, IaInvestingError)
        assert issubclass(IaInvestingError, Exception)

    def test_guardrail_violation_deep_hierarchy(self) -> None:
        assert issubclass(GuardrailViolationError, BusinessRejectionError)
        assert issubclass(BusinessRejectionError, IaInvestingError)
        assert issubclass(IaInvestingError, Exception)
