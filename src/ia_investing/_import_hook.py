from __future__ import annotations

import logging
import os
import sys
import traceback
import types
import warnings
from collections.abc import Sequence

from ia_investing._legacy_bridge import LegacyBridge

__all__ = ["LegacyImportGuard", "install_guard"]

logger = logging.getLogger("ia_investing.import_hook")

_STRICT = os.environ.get("IA_STRICT_MODE", "").lower() in ("1", "true", "yes")

_LEGACY_TOP_LEVEL = frozenset(
    {
        "agents",
        "backtesting",
        "connectors",
        "database",
        "data_quality",
        "domain",
        "evaluation",
        "metrics",
        "normalization",
        "observability",
        "parsers",
        "portfolio",
        "schemas",
        "workflows",
    }
)


class LegacyImportGuard:
    """Python meta-path hook that intercepts legacy top-level imports.

    When ``IA_STRICT_MODE`` is set, raises ``ImportError``.
    Otherwise logs a deprecation warning with a stack trace and lets
    the import proceed normally.
    """

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: types.ModuleType | None = None,
    ) -> None:
        top = fullname.split(".", 1)[0]
        if top not in _LEGACY_TOP_LEVEL:
            return None

        message = f"Import of legacy module '{fullname}' — use 'ia_investing.{fullname}' instead."

        if _STRICT:
            raise ImportError(f"Legacy imports are forbidden in strict mode: {message}")

        stack = "".join(traceback.format_stack(limit=6)[:-2])
        logger.warning("Legacy import: %s\n%s", fullname, stack)
        warnings.warn(
            message,
            DeprecationWarning,
            stacklevel=3,
        )

        return None


def install_guard() -> None:
    if not any(isinstance(hook, LegacyImportGuard) for hook in sys.meta_path):
        sys.meta_path.insert(0, LegacyImportGuard())


def wrap_legacy_module(name: str) -> None:
    if name in sys.modules and not isinstance(sys.modules[name], LegacyBridge):
        module = sys.modules[name]
        sys.modules[str(name)] = LegacyBridge(module)  # type: ignore[assignment]
