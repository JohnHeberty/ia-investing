from __future__ import annotations

import json
import logging
from datetime import date

from ..base import HttpClient
from ._bcb import MacroObservation, _parse_value

logger = logging.getLogger(__name__)

IBGE_SIDRA = "https://apisidra.ibge.gov.br/values/t/{table}/n1/all/v/{variable}/p/{period}/c{classification}/{last_n}"


async def get_gdp(
    quarter_count: int = 4,
    client: HttpClient | None = None,
) -> list[MacroObservation]:
    if client is None:
        client = HttpClient(timeout=30.0)

    table = 3844
    variable = 3759
    classification = "c62"
    last_n = f"last{quarter_count}"

    url = IBGE_SIDRA.format(
        table=table,
        variable=variable,
        period=f"last{quarter_count}Q",
        classification=classification,
        last_n=last_n,
    )

    raw = await client.get_text(url)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to decode JSON from IBGE SIDRA GDP table %d", table)
        return []

    results: list[MacroObservation] = []
    for item in data[1:]:
        period_str = item.get("D3N", "")
        value_str = item.get("V", "0")

        try:
            parts = period_str.split(" ")
            quarter = int(parts[0])
            year = int(parts[2])
            month = quarter * 3
            period_date = date(year, month, 1)
        except (IndexError, ValueError):
            continue

        results.append(
            MacroObservation(
                indicator_name="PIB",
                period_date=period_date,
                value=_parse_value(value_str) or 0.0,
                unit="R$ mil",
                source="IBGE",
                series_code=f"SIDRA_{table}",
            )
        )
    return sorted(results, key=lambda x: x.period_date)


async def get_industrial_production(
    month_count: int = 12,
    client: HttpClient | None = None,
) -> list[MacroObservation]:
    if client is None:
        client = HttpClient(timeout=30.0)

    table = 3653
    variable = 4375
    classification = "c112"
    last_n = f"last{month_count}"

    url = IBGE_SIDRA.format(
        table=table,
        variable=variable,
        period=f"last{month_count}M",
        classification=classification,
        last_n=last_n,
    )

    raw = await client.get_text(url)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to decode JSON from IBGE SIDRA industrial production table %d", table)
        return []

    results: list[MacroObservation] = []
    for item in data[1:]:
        period_str = item.get("D3N", "")
        value_str = item.get("V", "0")

        try:
            parts = period_str.split(" ")
            month_name = parts[0]
            year = int(parts[2])
            month_map = {
                "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4,
                "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
                "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
            }
            month_num = month_map.get(month_name.lower(), 1)
            period_date = date(year, month_num, 1)
        except (IndexError, ValueError):
            continue

        results.append(
            MacroObservation(
                indicator_name="Produção Industrial",
                period_date=period_date,
                value=_parse_value(value_str) or 0.0,
                unit="Índice",
                source="IBGE",
                series_code=f"SIDRA_{table}",
            )
        )
    return sorted(results, key=lambda x: x.period_date)
