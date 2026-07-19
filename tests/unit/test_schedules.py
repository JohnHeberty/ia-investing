from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from temporalio.client import ScheduleAlreadyRunningError, ScheduleOverlapPolicy

from apps.scheduler.main import (
    cvm_schedule_definition,
    paper_rebalance_schedule_definition,
    paper_reconciliation_schedule_definition,
    paper_valuation_schedule_definition,
    reconcile_schedules,
)


def test_cvm_schedule_has_stable_policy_and_queue() -> None:
    definition = cvm_schedule_definition(
        cnpj="02.474.103/0001-19",
        issuer_id="engie-brasil",
        year=2025,
        every=timedelta(hours=12),
    )

    assert definition.schedule_id == "cvm-dfp-engie-brasil-2025-dre_con"
    assert definition.schedule.policy.overlap is ScheduleOverlapPolicy.SKIP
    assert definition.schedule.policy.catchup_window == timedelta(hours=1)
    assert definition.schedule.policy.pause_on_failure is True
    assert definition.schedule.action.task_queue == "data-ingestion"


def test_paper_reconciliation_schedule_is_fail_closed_and_stable() -> None:
    definition = paper_reconciliation_schedule_definition(
        portfolio_id="portfolio-1",
        organization_id="organization-1",
        every=timedelta(hours=24),
    )
    assert definition.schedule_id == "paper-reconciliation-portfolio-1"
    assert definition.schedule.policy.overlap is ScheduleOverlapPolicy.SKIP
    assert definition.schedule.policy.pause_on_failure is True
    assert definition.schedule.action.task_queue == "portfolio-risk"


def test_paper_valuation_and_rebalance_schedules_are_fail_closed_and_stable() -> None:
    valuation = paper_valuation_schedule_definition(
        portfolio_id="portfolio-1",
        portfolio_version_id="version-7",
        organization_id="organization-1",
    )
    rebalance = paper_rebalance_schedule_definition(
        portfolio_id="portfolio-1",
        portfolio_version_id="version-7",
        input_sha256="a" * 64,
    )
    assert valuation.schedule_id == "paper-valuation-portfolio-1"
    assert rebalance.schedule_id == "paper-rebalance-portfolio-1"
    for definition in (valuation, rebalance):
        assert definition.schedule.policy.overlap is ScheduleOverlapPolicy.SKIP
        assert definition.schedule.policy.pause_on_failure is True
        assert definition.schedule.action.task_queue == "portfolio-risk"


@pytest.mark.asyncio
async def test_reconcile_creates_new_schedule() -> None:
    definition = cvm_schedule_definition(cnpj="1", issuer_id="issuer", year=2025)
    client = Mock()
    client.create_schedule = AsyncMock()

    result = await reconcile_schedules(client, [definition])

    assert result == {definition.schedule_id: "created"}
    client.create_schedule.assert_awaited_once_with(definition.schedule_id, definition.schedule)


@pytest.mark.asyncio
async def test_reconcile_updates_existing_schedule() -> None:
    definition = cvm_schedule_definition(cnpj="1", issuer_id="issuer", year=2025)
    client = Mock()
    client.create_schedule = AsyncMock(side_effect=ScheduleAlreadyRunningError())
    handle = Mock()
    handle.update = AsyncMock()
    client.get_schedule_handle.return_value = handle

    result = await reconcile_schedules(client, [definition])

    assert result == {definition.schedule_id: "updated"}
    handle.update.assert_awaited_once()
