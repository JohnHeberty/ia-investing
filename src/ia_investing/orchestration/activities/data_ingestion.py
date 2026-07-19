from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from temporalio import activity
from temporalio.exceptions import ApplicationError

from connectors.cvm._financials import StatementType, get_dfp
from data_quality._accounting import run_all_checks
from database.core import session_scope
from database.models.financials import FinancialStatement


@activity.defn(name="download_cvm_filing")
async def download_cvm_filing(cnpj: str, year: int, statement_type: str) -> list[dict[str, object]]:
    activity.heartbeat({"stage": "starting", "year": year, "statement_type": statement_type})
    try:
        selected_type = StatementType(statement_type)
    except ValueError as exc:
        raise ApplicationError(
            f"unsupported CVM statement type: {statement_type}",
            type="DataValidationError",
            non_retryable=True,
        ) from exc
    entries = await get_dfp(year, statement=selected_type, cnpj=cnpj)
    activity.heartbeat({"stage": "downloaded", "records": len(entries)})
    return [entry.to_dict() for entry in entries]


@activity.defn(name="parse_cvm_csv")
def parse_cvm_csv(raw_entries: list[dict[str, Any]], scale_factor: int) -> list[dict[str, Any]]:
    if scale_factor <= 0:
        raise ApplicationError("scale_factor must be positive", type="DataValidationError", non_retryable=True)
    required = {"cnpj", "dt_referencia", "cod_conta", "valor"}
    for index, entry in enumerate(raw_entries):
        missing = required - entry.keys()
        if missing:
            raise ApplicationError(
                f"record {index} is missing required fields: {sorted(missing)}",
                type="DataValidationError",
                non_retryable=True,
            )
    return raw_entries


@activity.defn(name="run_accounting_validations")
def run_accounting_validations(statement_type: str, record: dict[str, Any]) -> list[dict[str, Any]]:
    normalized_type = "DRE" if statement_type.startswith("DRE") else statement_type
    return [asdict(result) for result in run_all_checks(normalized_type, record)]


@activity.defn(name="store_financial_statements")
async def store_financial_statements(
    issuer_id: str,
    statement_type: str,
    records: list[dict[str, Any]],
    year: int,
) -> int:
    if not records:
        return 0
    try:
        issuer_uuid = UUID(issuer_id)
    except ValueError as exc:
        raise ApplicationError("issuer_id must be a UUID", type="DataValidationError", non_retryable=True) from exc

    period_end = date.fromisoformat(str(records[0]["dt_referencia"]))
    line_items = {str(record["cod_conta"]): record["valor"] for record in records}
    values = {
        "issuer_id": issuer_uuid,
        "statement_type": statement_type,
        "reporting_period_start": date(year, 1, 1),
        "reporting_period_end": period_end,
        "published_at": datetime.now(UTC),
        "currency_code": "BRL",
        "scale_factor": 1000,
        "line_items": line_items,
        "raw_data": records,
    }
    statement = insert(FinancialStatement).values(**values)
    statement = statement.on_conflict_do_update(
        constraint="uq_financial_statements_issuer_type_period",
        set_={key: value for key, value in values.items() if key != "issuer_id"},
    )
    async with session_scope() as session:
        await session.execute(statement)
    return len(records)


DATA_INGESTION_ACTIVITIES = (
    download_cvm_filing,
    parse_cvm_csv,
    run_accounting_validations,
    store_financial_statements,
)
