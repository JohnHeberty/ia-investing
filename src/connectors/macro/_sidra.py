from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import date

from ..base import HttpClient
from ._bcb import MacroObservation, _parse_value

logger = logging.getLogger(__name__)

IBGE_SIDRA = "https://apisidra.ibge.gov.br/values/t/{table}/n1/all/v/{variable}/p/{period}/c{classification}/{last_n}"

DEFAULT_MACRO_TIMEOUT = 30.0

_SIDRA_GDP_TABLE = 3844
_SIDRA_GDP_VARIABLE = 3759
_SIDRA_GDP_CLASSIFICATION = "c62"

_SIDRA_IP_TABLE = 3653
_SIDRA_IP_VARIABLE = 4375
_SIDRA_IP_CLASSIFICATION = "c112"

_MONTH_NAME_MAP = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


def _parse_quarter_period(period_str: str) -> date | None:
    try:
        parts = period_str.split(" ")
        quarter = int(parts[0])
        year = int(parts[2])
        month = quarter * 3
        return date(year, month, 1)
    except (IndexError, ValueError):
        return None


def _parse_month_period(period_str: str) -> date | None:
    try:
        parts = period_str.split(" ")
        month_name = parts[0]
        year = int(parts[2])
        month_num = _MONTH_NAME_MAP.get(month_name.lower(), 1)
        return date(year, month_num, 1)
    except (IndexError, ValueError):
        return None


async def _fetch_sidra(
    table: int,
    variable: int,
    classification: str,
    period_format: str,
    count: int,
    indicator_name: str,
    unit: str,
    parse_period: Callable[[str], date | None],
    client: HttpClient | None = None,
) -> list[MacroObservation]:
    if client is None:
        client = HttpClient(timeout=DEFAULT_MACRO_TIMEOUT)

    last_n = f"last{count}"
    url = IBGE_SIDRA.format(
        table=table,
        variable=variable,
        period=period_format,
        classification=classification,
        last_n=last_n,
    )

    raw = await client.get_text(url)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to decode JSON from IBGE SIDRA table %d", table)
        return []

    results: list[MacroObservation] = []
    for item in data[1:]:
        period_str = item.get("D3N", "")
        value_str = item.get("V")
        period_date = parse_period(period_str)
        value = _parse_value(value_str) if isinstance(value_str, str) else None
        if period_date is None or value is None:
            continue
        results.append(
            MacroObservation(
                indicator_name=indicator_name,
                period_date=period_date,
                value=value,
                unit=unit,
                source="IBGE",
                series_code=f"SIDRA_{table}",
            )
        )
    return sorted(results, key=lambda x: x.period_date)


async def get_gdp(
    quarter_count: int = 4,
    client: HttpClient | None = None,
) -> list[MacroObservation]:
    return await _fetch_sidra(
        table=_SIDRA_GDP_TABLE,
        variable=_SIDRA_GDP_VARIABLE,
        classification=_SIDRA_GDP_CLASSIFICATION,
        period_format=f"last{quarter_count}Q",
        count=quarter_count,
        indicator_name="PIB",
        unit="R$ mil",
        parse_period=_parse_quarter_period,
        client=client,
    )


async def get_industrial_production(
    month_count: int = 12,
    client: HttpClient | None = None,
) -> list[MacroObservation]:
    return await _fetch_sidra(
        table=_SIDRA_IP_TABLE,
        variable=_SIDRA_IP_VARIABLE,
        classification=_SIDRA_IP_CLASSIFICATION,
        period_format=f"last{month_count}M",
        count=month_count,
        indicator_name="Produção Industrial",
        unit="Índice",
        parse_period=_parse_month_period,
        client=client,
    )
