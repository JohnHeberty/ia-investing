"""Normalize raw CVM financial entries into canonical line-item dictionaries.

Maps CVM account codes (cod_conta) and description patterns to a unified
set of canonical keys used across the metrics engine and database models.
"""

from __future__ import annotations

from ._derived import compute_derived_metrics
from ._mappings import CVM_ACCOUNT_MAP
from ._normalizers import (
    normalize_bpa,
    normalize_bpp,
    normalize_dfc,
    normalize_dre,
)

__all__ = [
    "CVM_ACCOUNT_MAP",
    "compute_derived_metrics",
    "normalize_bpa",
    "normalize_bpp",
    "normalize_dfc",
    "normalize_dre",
]
