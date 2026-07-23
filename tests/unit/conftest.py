"""Shared test fixtures and collection-time patches for the unit test suite."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# cvxpy compatibility shim
# ---------------------------------------------------------------------------
# cvxpy >= 1.6 requires numpy.lib.array_utils (numpy >= 2.0).  When the
# runtime numpy is older the import fails at *collection* time, blocking
# every module that transitively touches ``portfolio`` or ``activities``.
# We install a lightweight stub so that unrelated tests can still be
# collected and executed.  Tests that truly need cvxpy must call
# ``pytest.importorskip("cvxpy")`` at module level.
try:
    import cvxpy  # noqa: F401
except (ImportError, ModuleNotFoundError):
    _stub = types.ModuleType("cvxpy")
    object.__setattr__(_stub, "__version__", "0.0.0-stub")
    object.__setattr__(_stub, "__path__", [])
    # Provide a generic attribute access so that attribute lookups don't raise.
    _stub.__getattr__ = lambda name: MagicMock()  # type: ignore[attr-defined]
    sys.modules.setdefault("cvxpy", _stub)
# Also stub sub-modules that cvxpy imports internally so that the stub
# itself doesn't blow up when executed as part of the import chain.
for _sub in ("cvxpy.atoms", "cvxpy.lin_ops", "cvxpy.lin_ops.backends"):
    sys.modules.setdefault(_sub, types.ModuleType(_sub))


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"


def _load_module_from_file(name: str, rel_path: str) -> Any:
    """Import a single .py file by path, bypassing package __init__."""
    path = SRC_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Session-scoped database fixtures (reusable across tests that need ORM)
# ---------------------------------------------------------------------------


@pytest.fixture()
def make_session() -> Any:
    """Return a factory that creates lightweight SQLAlchemy session mocks."""
    from unittest.mock import MagicMock

    session = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    session.flush = MagicMock()
    return session


@pytest.fixture()
def make_budget() -> dict[str, Any]:
    """Return a default budget dictionary for portfolio construction tests."""
    return {
        "max_weight": 0.40,
        "min_weight": 0.0,
        "max_turnover": 0.25,
        "min_cash_weight": 0.05,
        "max_cash_weight": 0.15,
    }


@pytest.fixture()
def make_output() -> dict[str, Any]:
    """Return a default output dictionary for optimization tests."""
    return {
        "status": "optimal",
        "weights": {"PETR4": 0.30, "VALE5": 0.30, "ITUB4": 0.30, "CASH": 0.10},
        "input_sha256": "a" * 64,
        "solver": "SCS",
        "diagnostics": {},
        "environment": "paper",
    }


@pytest.fixture()
def make_fact() -> dict[str, Any]:
    """Return a default financial-fact dictionary for scoring tests."""
    return {
        "quality": 0.8,
        "valuation": 0.6,
        "growth": 0.7,
        "leverage": 0.5,
        "momentum": 0.4,
        "dividend": 0.3,
    }
