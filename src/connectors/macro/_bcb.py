from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime

from ..base import HttpClient

logger = logging.getLogger(__name__)

BCB_BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"

SERIES_SELIC = 432
SERIES_IPCA = 433
SERIES_IPCA_MONTHLY = 7062
SERIES_USD_BRL = 1


@dataclass(slots=True)
class MacroObservation:
    indicator_name: str
    period_date: date
    value: float
    unit: str
    source: str
    series_code: int | str


def _parse_bcb_date(raw: str) -> date | None:
    try:
        return datetime.strptime(raw.strip(), "%d/%m/%Y").date()
    except (ValueError, AttributeError):
        return None


def _parse_value(raw: str) -> float | None:
    try:
        return float(raw.strip().replace(",", "."))
    except (ValueError, AttributeError):
        return None


async def get_bcb_series(
    series_code: int,
    start_date: date,
    end_date: date,
    client: HttpClient | None = None,
    indicator_name: str = "",
    unit: str = "",
) -> list[MacroObservation]:
    if client is None:
        client = HttpClient(timeout=30.0)

    url = BCB_BASE.format(code=series_code)
    params = {
        "formato": "json",
        "dataInicial": start_date.strftime("%d/%m/%Y"),
        "dataFinal": end_date.strftime("%d/%m/%Y"),
    }

    raw = await client.get_text(url, params=params)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to decode JSON from BCB series %s", series_code)
        return []

    results: list[MacroObservation] = []
    for item in data:
        period_date = _parse_bcb_date(item["data"])
        value = _parse_value(item["valor"])
        if period_date is None or value is None:
            continue
        results.append(
            MacroObservation(
                indicator_name=indicator_name or f"BCB_{series_code}",
                period_date=period_date,
                value=value,
                unit=unit,
                source="BCB",
                series_code=series_code,
            )
        )
    return results


async def get_selic(
    start_date: date,
    end_date: date,
    client: HttpClient | None = None,
) -> list[MacroObservation]:
    return await get_bcb_series(
        SERIES_SELIC,
        start_date,
        end_date,
        client,
        indicator_name="SELIC",
        unit="% a.a.",
    )


async def get_ipca(
    start_date: date,
    end_date: date,
    client: HttpClient | None = None,
) -> list[MacroObservation]:
    return await get_bcb_series(
        SERIES_IPCA,
        start_date,
        end_date,
        client,
        indicator_name="IPCA",
        unit="% a.m.",
    )


async def get_ipca_monthly(
    year: int,
    client: HttpClient | None = None,
) -> list[MacroObservation]:
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    return await get_bcb_series(
        SERIES_IPCA_MONTHLY,
        start,
        end,
        client,
        indicator_name="IPCA_Mensal",
        unit="% a.m.",
    )


async def get_usd_brl(
    start_date: date,
    end_date: date,
    client: HttpClient | None = None,
) -> list[MacroObservation]:
    return await get_bcb_series(
        SERIES_USD_BRL,
        start_date,
        end_date,
        client,
        indicator_name="USD/BRL",
        unit="BRL",
    )
