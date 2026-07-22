from pathlib import Path


def test_temporal_registry_excludes_mock_execution_paths():
    root = Path(__file__).resolve().parents[2]
    registry = (root / "src/ia_investing/orchestration/registry.py").read_text(encoding="utf-8")

    assert "research_mock" not in registry
    assert "run_configured_agent" not in registry
    assert '"document-processing"' not in registry
    assert '"research-agents"' in registry
    assert "RunAgentWorkflow" in registry
    assert "AGENT_RUNTIME_ACTIVITIES" in registry


def test_schedules_start_registered_public_workflows():
    root = Path(__file__).resolve().parents[2]
    schedules = (root / "src/ia_investing/orchestration/schedules.py").read_text(encoding="utf-8")

    assert 'workflow="IngestCVMWorkflow"' in schedules
    assert 'workflow="PaperValuationWorkflow"' in schedules
    assert 'workflow="PaperReconciliationWorkflow"' in schedules
    assert "ScheduleOverlapPolicy.SKIP" in schedules
    assert "pause_on_failure=True" in schedules


def test_transactional_outbox_is_registered_and_scheduled():
    root = Path(__file__).resolve().parents[2]
    registry = (root / "src/ia_investing/orchestration/registry.py").read_text(encoding="utf-8")
    schedules = (root / "src/ia_investing/orchestration/schedules.py").read_text(encoding="utf-8")
    api = (root / "src/apps/api/routes/institutional.py").read_text(encoding="utf-8")
    models = (root / "src/database/models/operations.py").read_text(encoding="utf-8")

    assert "DispatchOperationsWorkflow" in registry
    assert "OPERATION_DISPATCH_ACTIVITIES" in registry
    assert 'schedule_id="operation-outbox-dispatch"' in schedules
    assert "OperationDispatchOutbox" in api
    assert 'topic="agent-run"' in api
    assert '__tablename__ = "operation_dispatch_outbox"' in models
