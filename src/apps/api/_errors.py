from __future__ import annotations

from fastapi import HTTPException

from ia_investing.application.errors import (
    BusinessRejectionError,
    IaInvestingError,
    RetryableInfrastructureError,
    ValidationError,
)


def map_error(exc: Exception) -> HTTPException:
    """Map domain exceptions to HTTP status codes.

    Hierarchy:
      404 — LookupError (not found)
      403 — PermissionError (forbidden)
      409 — ValueError / InvalidTransition / Conflict / Idempotency
      422 — BusinessRejectionError / ValidationError
      503 — RetryableInfrastructureError (transient, client should retry)
      500 — everything else
    """
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, BusinessRejectionError | ValidationError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, RetryableInfrastructureError):
        return HTTPException(status_code=503, detail=str(exc) or "Service temporarily unavailable")
    if isinstance(exc, ValueError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, IaInvestingError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail="Internal server error")
