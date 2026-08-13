"""Database compatibility layer — re-exports from canonical locations."""

from database.core import (  # noqa: F401
    close_db,
    get_async_session,
    session_scope,
)
from database.models import *  # noqa: F403
