from __future__ import annotations

import logging
import os
import sys
import types
import warnings
from typing import Any

__all__ = ["TRACKER", "LegacyBridge", "LegacyModuleError"]

logger = logging.getLogger("ia_investing.legacy_bridge")

_TRACKED_ACCESS: dict[str, list[str]] = {}

_STRICT = os.environ.get("IA_STRICT_MODE", "").lower() in ("1", "true", "yes")


class LegacyModuleError(ImportError):
    """Raised when a legacy module is accessed in strict mode."""


class LegacyBridge:
    """Wraps a legacy module, logging all attribute access and surfacing deprecation warnings.

    In strict mode (IA_STRICT_MODE=1) every access raises LegacyModuleError.
    """

    def __init__(self, module: types.ModuleType) -> None:
        self._module = module
        legacy_name = module.__name__
        _TRACKED_ACCESS.setdefault(legacy_name, [])

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            return object.__getattribute__(self, name)

        module = self._module
        legacy_name = module.__name__

        if _STRICT:
            raise LegacyModuleError(
                f"Access to legacy module '{legacy_name}.{name}' is blocked by IA_STRICT_MODE. "
                f"Use 'ia_investing.{legacy_name}' instead."
            )

        _TRACKED_ACCESS[legacy_name].append(name)
        logger.warning(
            "Deprecated access to '%s.%s' via legacy bridge. Migrate to 'ia_investing.%s.%s'.",
            legacy_name,
            name,
            legacy_name,
            name,
        )
        warnings.warn(
            f"'{legacy_name}.{name}' is deprecated. Use 'ia_investing.{legacy_name}.{name}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        return getattr(module, name)

    @staticmethod
    def install(module: types.ModuleType) -> LegacyBridge:
        bridge = LegacyBridge(module)
        sys.modules[module.__name__] = bridge  # type: ignore[assignment]
        return bridge


TRACKER = _TRACKED_ACCESS
