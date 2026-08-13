"""Unit tests for workflows._ingest_cvm — IngestCVMWorkflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows._ingest_cvm import IngestCVMInput, IngestCVMOutput, IngestCVMWorkflow

TASK_QUEUE = "test-ingest-cvm"


@pytest.mark.unit
class TestIngestCVMInput:
    def test_defaults(self):
        inp = IngestCVMInput(cnpj="123", year=2024, statement_type="DRE")
        assert inp.cnpj == "123"
        assert inp.year == 2024
        assert inp.statement_type == "DRE"
        assert inp.issuer_id == ""
        assert inp.scale_factor == 1000
        assert inp.schedule_id == ""

    def test_custom_values(self):
        inp = IngestCVMInput(
            cnpj="456",
            year=2023,
            statement_type="BPP",
            issuer_id="iss-1",
            scale_factor=100,
            schedule_id="sch-1",
        )
        assert inp.issuer_id == "iss-1"
        assert inp.scale_factor == 100
        assert inp.schedule_id == "sch-1"

    def test_equality(self):
        a = IngestCVMInput(cnpj="123", year=2024, statement_type="DRE")
        b = IngestCVMInput(cnpj="123", year=2024, statement_type="DRE")
        assert a == b


@pytest.mark.unit
class TestIngestCVMOutput:
    def test_defaults(self):
        out = IngestCVMOutput(issuer_id="i", statement_type="DRE", year=2024)
        assert out.records_inserted == 0
        assert out.validation_results == []
        assert out.errors == []

    def test_with_values(self):
        out = IngestCVMOutput(
            issuer_id="i",
            statement_type="DRE",
            year=2024,
            records_inserted=10,
            validation_results=[],
            errors=["err"],
        )
        assert out.records_inserted == 10
        assert out.errors == ["err"]


@dataclass(slots=True)
class FakeValidationResult:
    check_name: str = ""
    passed: bool = True
    entity_type: str = "issuer"
    entity_id: str = "test"
    details: dict[str, Any] = field(default_factory=dict)
    severity: str = "error"


def _make_activities(
    download_result: Any = None,
    parse_result: Any = None,
    validate_result: Any = None,
    store_result: int = 0,
):
    """Create activity functions with captured return values."""
    captured_publish: list[dict[str, Any]] = []
    captured_record: dict[str, Any] = {}

    @activity.defn(name="download_cvm_filing")
    async def fake_download(cnpj: str, year: int, statement_type: str) -> Any:
        return download_result if download_result is not None else []

    @activity.defn(name="parse_cvm_csv")
    async def fake_parse(records: Any, scale_factor: int) -> Any:
        return parse_result if parse_result is not None else []

    @activity.defn(name="run_accounting_validations")
    async def fake_validate(statement_type: str, records: Any) -> Any:
        return validate_result if validate_result is not None else []

    @activity.defn(name="store_financial_statements")
    async def fake_store(issuer_id: str, statement_type: str, records: Any, year: int) -> int:
        return store_result

    @activity.defn(name="publish_event")
    async def fake_publish(topic: str, payload: dict) -> None:
        captured_publish.append({"topic": topic, "payload": payload})

    @activity.defn(name="record_schedule_run")
    async def fake_record(input: dict) -> None:
        captured_record.update(input)

    activities = [fake_download, fake_parse, fake_validate, fake_store, fake_publish, fake_record]
    return activities, captured_publish, captured_record


@pytest.mark.unit
class TestIngestCVMWorkflow:
    @pytest.mark.asyncio
    async def test_happy_path_no_errors(self):
        acts, publish, _record = _make_activities(
            download_result=[{"row": 1}],
            parse_result=[{"parsed": True}],
            validate_result=[FakeValidationResult(check_name="rev", passed=True, severity="error")],
            store_result=5,
        )

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[IngestCVMWorkflow]):
                result = await env.client.execute_workflow(
                    IngestCVMWorkflow.run,
                    IngestCVMInput(cnpj="123", year=2024, statement_type="DRE", issuer_id="iss-1"),
                    id="test-ingest-cvm-1",
                    task_queue=TASK_QUEUE,
                )

        assert result.records_inserted == 5
        assert result.errors == []
        assert publish[0]["payload"]["validation_passed"] is True

    @pytest.mark.asyncio
    async def test_validation_errors_populated(self):
        acts, _publish, _record = _make_activities(
            download_result=[{"row": 1}],
            parse_result=[{"parsed": True}],
            validate_result=[
                FakeValidationResult(
                    check_name="rev_check",
                    passed=False,
                    severity="error",
                    details={"message": "Revenue mismatch"},
                ),
            ],
            store_result=3,
        )

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[IngestCVMWorkflow]):
                result = await env.client.execute_workflow(
                    IngestCVMWorkflow.run,
                    IngestCVMInput(cnpj="456", year=2023, statement_type="BPP", issuer_id="iss-2"),
                    id="test-ingest-cvm-2",
                    task_queue=TASK_QUEUE,
                )

        assert len(result.errors) == 1
        assert "rev_check" in result.errors[0]
        assert "Revenue mismatch" in result.errors[0]

    @pytest.mark.asyncio
    async def test_schedule_id_records_run(self):
        acts, _publish, record = _make_activities(store_result=0)

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[IngestCVMWorkflow]):
                await env.client.execute_workflow(
                    IngestCVMWorkflow.run,
                    IngestCVMInput(
                        cnpj="789",
                        year=2022,
                        statement_type="DFC",
                        issuer_id="iss-3",
                        schedule_id="sch-99",
                    ),
                    id="test-ingest-cvm-3",
                    task_queue=TASK_QUEUE,
                )

        assert record["schedule_id"] == "sch-99"
        assert record["status"] == "completed"

    @pytest.mark.asyncio
    async def test_no_schedule_id_skips_record(self):
        acts, _publish, record = _make_activities(store_result=0)

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[IngestCVMWorkflow]):
                await env.client.execute_workflow(
                    IngestCVMWorkflow.run,
                    IngestCVMInput(cnpj="789", year=2022, statement_type="DFC", issuer_id="iss-3"),
                    id="test-ingest-cvm-4",
                    task_queue=TASK_QUEUE,
                )

        assert record == {}

    @pytest.mark.asyncio
    async def test_validation_severity_warning_not_error(self):
        acts, _publish, _record = _make_activities(
            download_result=[{"row": 1}],
            parse_result=[{"parsed": True}],
            validate_result=[
                FakeValidationResult(
                    check_name="warn_check",
                    passed=False,
                    severity="warning",
                    details={"message": "Minor issue"},
                ),
            ],
            store_result=1,
        )

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[IngestCVMWorkflow]):
                result = await env.client.execute_workflow(
                    IngestCVMWorkflow.run,
                    IngestCVMInput(cnpj="000", year=2021, statement_type="DRA", issuer_id="iss-4"),
                    id="test-ingest-cvm-5",
                    task_queue=TASK_QUEUE,
                )

        assert result.errors == []
        assert len(result.validation_results) == 1

    @pytest.mark.asyncio
    async def test_multiple_validation_errors(self):
        acts, _publish, _record = _make_activities(
            validate_result=[
                FakeValidationResult(check_name="c1", passed=False, severity="error", details={"message": "err1"}),
                FakeValidationResult(check_name="c2", passed=False, severity="error", details={"message": "err2"}),
            ],
            store_result=0,
        )

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[IngestCVMWorkflow]):
                result = await env.client.execute_workflow(
                    IngestCVMWorkflow.run,
                    IngestCVMInput(cnpj="111", year=2020, statement_type="DRE", issuer_id="iss-5"),
                    id="test-ingest-cvm-6",
                    task_queue=TASK_QUEUE,
                )

        assert len(result.errors) == 2
