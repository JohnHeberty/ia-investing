"""Tests for F2-PR06.3 — RestatementLog diff tracking."""

from decimal import Decimal
from uuid import uuid4

from database.models.financial_facts import RestatementLog


def test_restatement_log_model_exists() -> None:
    """RestatementLog model can be instantiated."""
    log = RestatementLog(
        superseded_fact_id=uuid4(),
        new_fact_id=uuid4(),
        account_code="1.01",
        old_value=Decimal("1000.00"),
        new_value=Decimal("1200.00"),
        old_value_status="reported",
        new_value_status="reported",
        revision_number=2,
    )
    assert log.account_code == "1.01"
    assert log.old_value == Decimal("1000.00")
    assert log.new_value == Decimal("1200.00")


def test_restatement_log_null_value_change() -> None:
    """RestatementLog supports null values for missing status."""
    log = RestatementLog(
        superseded_fact_id=uuid4(),
        new_fact_id=uuid4(),
        account_code="2.01",
        old_value=Decimal("500.00"),
        new_value=None,
        old_value_status="reported",
        new_value_status="missing",
        revision_number=3,
    )
    assert log.new_value is None
    assert log.new_value_status == "missing"
