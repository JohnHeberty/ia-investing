from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Literal, cast

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from data_quality._accounting import ValidationResult
    from ia_investing.orchestration.policies import DEFAULT_ACTIVITY_RETRY_POLICY, EXTERNAL_IO_RETRY_POLICY
    from workflows._schedule_run import complete_schedule_run, fail_schedule_run, start_schedule_run


@dataclass(slots=True)
class IngestCVMInput:
    cnpj: str
    year: int
    statement_type: str
    issuer_id: str = ""
    scale_factor: int = 1000
    schedule_id: str = ""


@dataclass(slots=True)
class IngestCVMOutput:
    issuer_id: str
    statement_type: str
    year: int
    records_inserted: int = 0
    validation_results: list[ValidationResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@workflow.defn
class IngestCVMWorkflow:
    @workflow.run
    async def run(self, input: IngestCVMInput) -> IngestCVMOutput:
        await start_schedule_run(input.schedule_id)
        try:
            output = await self._ingest(input)
        except Exception as exc:
            await fail_schedule_run(input.schedule_id, exc)
            raise
        await complete_schedule_run(
            input.schedule_id,
            {
                "issuer_id": input.issuer_id,
                "statement_type": input.statement_type,
                "year": input.year,
                "records_inserted": output.records_inserted,
                "errors": len(output.errors),
            },
        )
        return output

    async def _ingest(self, input: IngestCVMInput) -> IngestCVMOutput:
        output = IngestCVMOutput(
            issuer_id=input.issuer_id,
            statement_type=input.statement_type,
            year=input.year,
        )

        raw_entries = await workflow.execute_activity(
            "download_cvm_filing",
            args=[input.cnpj, input.year, input.statement_type],
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=EXTERNAL_IO_RETRY_POLICY,
        )

        parsed_records = await workflow.execute_activity(
            "parse_cvm_csv",
            args=[raw_entries, input.scale_factor],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=DEFAULT_ACTIVITY_RETRY_POLICY,
        )

        raw_validation_results: list[dict[str, Any]] = await workflow.execute_activity(
            "run_accounting_validations",
            args=[input.statement_type, parsed_records],
            result_type=list,
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=DEFAULT_ACTIVITY_RETRY_POLICY,
        )
        validation_results = [
            ValidationResult(
                check_name=str(item["check_name"]),
                passed=bool(item["passed"]),
                entity_type=str(item["entity_type"]),
                entity_id=str(item["entity_id"]),
                details=cast(dict[str, Any], item.get("details", {})),
                severity=cast(Literal["error", "warning", "info"], item.get("severity", "warning")),
            )
            for item in raw_validation_results
        ]

        output.validation_results = validation_results

        errors = [r for r in validation_results if not r.passed and r.severity == "error"]
        if errors:
            output.errors = [f"{e.check_name}: {e.details}" for e in errors]

        stored_count = await workflow.execute_activity(
            "store_financial_statements",
            args=[input.issuer_id, input.statement_type, parsed_records, input.year],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=DEFAULT_ACTIVITY_RETRY_POLICY,
        )
        output.records_inserted = stored_count

        await workflow.execute_activity(
            "publish_event",
            args=[
                "cvm.ingested",
                {
                    "issuer_id": input.issuer_id,
                    "statement_type": input.statement_type,
                    "year": input.year,
                    "records_count": stored_count,
                    "validation_passed": len(errors) == 0,
                },
            ],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=DEFAULT_ACTIVITY_RETRY_POLICY,
        )

        return output
