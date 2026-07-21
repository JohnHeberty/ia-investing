from __future__ import annotations

from fastapi import Depends

from apps.api.security import AuthContext, get_auth_context


async def get_current_user(
    context: AuthContext = Depends(get_auth_context),
) -> AuthContext:
    return context
