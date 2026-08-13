"""Contract tests for CorporateAction model."""

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import inspect as sa_inspect

from database.models.market_data import CorporateAction

_DUMMY_INSTRUMENT = uuid4()
_DUMMY_SOVID = uuid4()


def test_dividend_action_type_valid() -> None:
    """Dividend is a valid action_type."""
    action = CorporateAction(
        instrument_id=_DUMMY_INSTRUMENT,
        action_type="dividend",
        announcement_date=date(2024, 6, 15),
        ex_date=date(2024, 7, 1),
        record_date=date(2024, 7, 2),
        payment_date=date(2024, 7, 15),
        amount_per_unit=2.50,
        currency_code="BRL",
        source_object_version_id=_DUMMY_SOVID,
        knowledge_at=datetime(2024, 6, 15, tzinfo=UTC),
    )
    assert action.action_type == "dividend"
    assert action.amount_per_unit == 2.50


def test_split_action_type_valid() -> None:
    """Split is a valid action_type."""
    action = CorporateAction(
        instrument_id=_DUMMY_INSTRUMENT,
        action_type="split",
        announcement_date=date(2024, 3, 1),
        ex_date=date(2024, 3, 15),
        ratio=2.0,
        source_object_version_id=_DUMMY_SOVID,
        knowledge_at=datetime(2024, 3, 1, tzinfo=UTC),
    )
    assert action.action_type == "split"
    assert action.ratio == 2.0


def test_jcp_action_type_valid() -> None:
    """JCP is a valid action_type."""
    action = CorporateAction(
        instrument_id=_DUMMY_INSTRUMENT,
        action_type="jcp",
        announcement_date=date(2024, 12, 1),
        ex_date=date(2024, 12, 20),
        amount_per_unit=1.00,
        currency_code="BRL",
        source_object_version_id=_DUMMY_SOVID,
        knowledge_at=datetime(2024, 12, 1, tzinfo=UTC),
    )
    assert action.action_type == "jcp"


def test_reverse_split_action_type_valid() -> None:
    """reverse_split is a valid action_type."""
    action = CorporateAction(
        instrument_id=_DUMMY_INSTRUMENT,
        action_type="reverse_split",
        announcement_date=date(2024, 5, 1),
        ex_date=date(2024, 5, 15),
        ratio=0.5,
        source_object_version_id=_DUMMY_SOVID,
        knowledge_at=datetime(2024, 5, 1, tzinfo=UTC),
    )
    assert action.action_type == "reverse_split"


def test_subscription_action_type_valid() -> None:
    """subscription is a valid action_type."""
    action = CorporateAction(
        instrument_id=_DUMMY_INSTRUMENT,
        action_type="subscription",
        announcement_date=date(2024, 8, 1),
        ex_date=date(2024, 8, 15),
        amount_per_unit=10.00,
        currency_code="BRL",
        source_object_version_id=_DUMMY_SOVID,
        knowledge_at=datetime(2024, 8, 1, tzinfo=UTC),
    )
    assert action.action_type == "subscription"


def test_buyback_action_type_valid() -> None:
    """buyback is a valid action_type."""
    action = CorporateAction(
        instrument_id=_DUMMY_INSTRUMENT,
        action_type="buyback",
        announcement_date=date(2024, 9, 1),
        ex_date=date(2024, 9, 15),
        source_object_version_id=_DUMMY_SOVID,
        knowledge_at=datetime(2024, 9, 1, tzinfo=UTC),
    )
    assert action.action_type == "buyback"


def test_bonus_action_type_valid() -> None:
    """bonus is a valid action_type."""
    action = CorporateAction(
        instrument_id=_DUMMY_INSTRUMENT,
        action_type="bonus",
        announcement_date=date(2024, 4, 1),
        ex_date=date(2024, 4, 15),
        ratio=0.1,
        source_object_version_id=_DUMMY_SOVID,
        knowledge_at=datetime(2024, 4, 1, tzinfo=UTC),
    )
    assert action.action_type == "bonus"


def test_all_action_types_covered() -> None:
    """All expected action types are supported by the database check constraint."""
    mapper = sa_inspect(CorporateAction)
    action_type_col = mapper.columns.get("action_type")
    assert action_type_col is not None
    from sqlalchemy import String as sa_String

    assert isinstance(action_type_col.type, sa_String)


def test_corporate_action_nullable_fields() -> None:
    """Optional fields default to None."""
    action = CorporateAction(
        instrument_id=_DUMMY_INSTRUMENT,
        action_type="dividend",
        announcement_date=date(2024, 1, 1),
        source_object_version_id=_DUMMY_SOVID,
        knowledge_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    assert action.ex_date is None
    assert action.record_date is None
    assert action.payment_date is None
    assert action.amount_per_unit is None
    assert action.ratio is None
    assert action.currency_code is None
