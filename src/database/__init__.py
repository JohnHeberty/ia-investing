import warnings

warnings.warn(
    "Importing from 'database' directly is deprecated. Use 'ia_investing.database' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from .config import get_settings  # noqa: E402
from .core import close_db, get_async_session, session_scope  # noqa: E402

__all__ = ["close_db", "get_async_session", "get_settings", "session_scope"]
