from __future__ import annotations

from fastapi import HTTPException

from apps.api.security import AuthContext
from ia_investing.domain.identity import InstitutionalAccessContext


def context_from(auth: AuthContext) -> InstitutionalAccessContext:
    """Build an InstitutionalAccessContext from an AuthContext.

    Raises HTTPException(403) if the auth context lacks an organization.
    """
    if auth.organization_id is None:
        raise HTTPException(status_code=403, detail="institutional organization context is required")
    return InstitutionalAccessContext(auth.subject, auth.organization_id, auth.team_ids, auth.permissions, "paper")
