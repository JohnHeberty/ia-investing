"""Tests for apps.api._errors — HTTP error mapping."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from apps.api._errors import map_error
from ia_investing.application.errors import (
    BusinessRejectionError,
    IaInvestingError,
    RetryableInfrastructureError,
    ValidationError,
)


class TestMapError:
    @pytest.mark.parametrize(
        "exc, expected_status",
        [
            (LookupError("not found"), 404),
            (PermissionError("denied"), 403),
            (BusinessRejectionError("bad request"), 422),
            (ValidationError("invalid"), 422),
            (RetryableInfrastructureError("timeout"), 503),
            (ValueError("conflict"), 409),
            (IaInvestingError("some error"), 409),
            (RuntimeError("unexpected"), 500),
            (Exception("generic"), 500),
        ],
    )
    def test_maps_exception_to_correct_status(self, exc: Exception, expected_status: int) -> None:
        result = map_error(exc)
        assert isinstance(result, HTTPException)
        assert result.status_code == expected_status

    def test_lookup_error_preserves_message(self) -> None:
        result = map_error(LookupError("instrument XYZ not found"))
        assert result.detail == "instrument XYZ not found"

    def test_permission_error_preserves_message(self) -> None:
        result = map_error(PermissionError("missing portfolio:read"))
        assert result.detail == "missing portfolio:read"

    def test_business_rejection_preserves_message(self) -> None:
        result = map_error(BusinessRejectionError("mandate violated"))
        assert result.detail == "mandate violated"

    def test_validation_error_preserves_message(self) -> None:
        result = map_error(ValidationError("invalid date range"))
        assert result.detail == "invalid date range"

    def test_retryable_infra_with_empty_message_uses_default(self) -> None:
        result = map_error(RetryableInfrastructureError())
        assert result.detail == "Service temporarily unavailable"

    def test_retryable_infra_preserves_message(self) -> None:
        result = map_error(RetryableInfrastructureError("connection refused"))
        assert result.detail == "connection refused"

    def test_value_error_preserves_message(self) -> None:
        result = map_error(ValueError("duplicate key"))
        assert result.detail == "duplicate key"

    def test_ia_investing_error_preserves_message(self) -> None:
        result = map_error(IaInvestingError("business logic error"))
        assert result.detail == "business logic error"

    def test_generic_exception_returns_500(self) -> None:
        result = map_error(RuntimeError("something broke"))
        assert result.status_code == 500
        assert result.detail == "Internal server error"

    def test_subclass_of_lookup_error(self) -> None:
        class MyLookupError(LookupError):
            pass

        result = map_error(MyLookupError("sub"))
        assert result.status_code == 404

    def test_subclass_of_value_error(self) -> None:
        class MyValueError(ValueError):
            pass

        result = map_error(MyValueError("sub"))
        assert result.status_code == 409
