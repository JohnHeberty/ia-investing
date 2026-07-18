"""Conector B3 — acesso unificado a dados da Bolsa 3."""

from __future__ import annotations

from ._cotahist import (
    CotahistTrade,
    get_cotahist_csv,
    get_cotahist_day,
    get_cotahist_month,
    get_cotahist_year,
)

__all__ = [
    "CotahistTrade",
    "get_cotahist_csv",
    "get_cotahist_day",
    "get_cotahist_month",
    "get_cotahist_year",
]
