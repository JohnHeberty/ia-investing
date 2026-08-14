"""Banco Central do Brasil — Sistema Gerenciador de Séries Temporais."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime

from ..base import HttpClient, HttpClientProtocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SGSObservation:
    date: date
    value: float


class BCBSGSClient:
    """Client for BCB SGS API (macro time series)."""

    BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata"

    def __init__(self, *, http: HttpClientProtocol | None = None) -> None:
        self._http = http or HttpClient(timeout=30, max_retries=3)

    async def fetch_series(
        self,
        *,
        series_code: int,
        start_date: date,
        end_date: date,
    ) -> list[SGSObservation]:
        """Fetch a time series from BCB SGS."""
        url = f"{self.BASE_URL}/{series_code}/dados"
        params: dict[str, str] = {
            "formato": "json",
            "dataInicial": start_date.strftime("%d/%m/%Y"),
            "dataFinal": end_date.strftime("%d/%m/%Y"),
        }
        raw = await self._http.get_text(url, params=params)
        return _parse_sgs_response(raw)


def _parse_sgs_response(raw: str) -> list[SGSObservation]:
    """Parse JSON response from BCB SGS API into observations."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("BCB SGS returned invalid JSON")
        return []

    if not isinstance(data, list):
        logger.warning("BCB SGS response is not a list")
        return []

    observations: list[SGSObservation] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        raw_date = item.get("data")
        raw_value = item.get("valor")
        if not isinstance(raw_date, str) or not isinstance(raw_value, str):
            continue
        parsed_date = _parse_sgs_date(raw_date)
        parsed_value = _parse_value(raw_value)
        if parsed_date is not None and parsed_value is not None:
            observations.append(SGSObservation(date=parsed_date, value=parsed_value))

    return observations


def _parse_sgs_date(raw: str) -> date | None:
    """Parse BCB date string (dd/mm/yyyy) into a date object."""
    if not isinstance(raw, str):
        return None
    try:
        return datetime.strptime(raw.strip(), "%d/%m/%Y").date()
    except (ValueError, TypeError):
        return None


def _parse_value(raw: str) -> float | None:
    """Parse BCB numeric value (comma-separated decimals)."""
    if not isinstance(raw, str):
        return None
    try:
        return float(raw.strip().replace(",", "."))
    except (ValueError, TypeError):
        return None
