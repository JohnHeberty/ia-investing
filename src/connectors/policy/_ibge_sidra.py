"""IBGE — Sistema de Recuperação de Dados Agregados."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from ..base import HttpClient, HttpClientProtocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SIDRATableMetadata:
    id: int
    nome: str
    universo: str


class IBGESIDRAClient:
    """Client for IBGE SIDRA API (aggregated data)."""

    BASE_URL = "https://apisidra.ibge.gov.br"

    def __init__(self, *, http: HttpClientProtocol | None = None) -> None:
        self._http = http or HttpClient(timeout=30, max_retries=3)

    async def fetch_table(
        self,
        *,
        table_id: int,
        variables: list[int],
        territorial_level: int = 1,
        period: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch data from a SIDRA table.

        Parameters
        ----------
        table_id:
            The SIDRA table identifier.
        variables:
            Variable IDs to fetch.
        territorial_level:
            Territorial aggregation level (1 = Brasil, 2 = Região, etc.).
        period:
            Optional period filter (e.g. ``"all"`` or ``"last 4 quarters"``).
        """
        if not variables:
            raise ValueError("At least one variable ID is required")

        n1 = f"n{territorial_level}" if territorial_level >= 1 else "n1"
        vars_param = ",".join(str(v) for v in variables)
        url = f"{self.BASE_URL}/tabela/{table_id}/periodos/{period or 'all'}/variaveis/{vars_param}?localities={n1}"
        raw = await self._http.get_text(url)
        return _parse_sidra_response(raw)

    async def fetch_table_with_periods(
        self,
        *,
        table_id: int,
        variables: list[int],
        territorial_level: int = 1,
        periods: list[str],
    ) -> list[dict[str, Any]]:
        """Fetch data from a SIDRA table with explicit periods."""
        if not variables:
            raise ValueError("At least one variable ID is required")
        if not periods:
            raise ValueError("At least one period is required")

        n1 = f"n{territorial_level}" if territorial_level >= 1 else "n1"
        vars_param = ",".join(str(v) for v in variables)
        periods_param = ",".join(periods)
        url = f"{self.BASE_URL}/tabela/{table_id}/periodos/{periods_param}/variaveis/{vars_param}?localities={n1}"
        raw = await self._http.get_text(url)
        return _parse_sidra_response(raw)


def _parse_sidra_response(raw: str) -> list[dict[str, Any]]:
    """Parse JSON response from SIDRA API."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("SIDRA returned invalid JSON")
        return []

    if not isinstance(data, list):
        logger.warning("SIDRA response is not a list")
        return []

    return [item for item in data if isinstance(item, dict)]
