from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from data_quality._accounting import ValidationResult


@dataclass(slots=True)
class IngestCVMInput:
    cnpj: str
    year: int
    statement_type: str
    issuer_id: str = ""
    scale_factor: int = 1000


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
        output = IngestCVMOutput(
            issuer_id=input.issuer_id,
            statement_type=input.statement_type,
            year=input.year,
        )

        raw_entries = await workflow.execute_activity(
            "download_cvm_filing",
            args=[input.cnpj, input.year, input.statement_type],
            start_to_close_timeout=timedelta(seconds=120),
        )

        parsed_records = await workflow.execute_activity(
            "parse_cvm_csv",
            args=[raw_entries, input.scale_factor],
            start_to_close_timeout=timedelta(seconds=60),
        )

        validation_results: list[ValidationResult] = []
        for record in parsed_records:
            checks = await workflow.execute_activity(
                "run_accounting_validations",
                args=[input.statement_type, record],
                start_to_close_timeout=timedelta(seconds=30),
            )
            validation_results.extend(checks)

        output.validation_results = validation_results

        errors = [r for r in validation_results if not r.passed and r.severity == "error"]
        if errors:
            output.errors = [f"{e.check_name}: {e.details}" for e in errors]

        stored_count = await workflow.execute_activity(
            "store_financial_statements",
            args=[input.issuer_id, input.statement_type, parsed_records, input.year],
            start_to_close_timeout=timedelta(seconds=60),
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
        )

        return output
