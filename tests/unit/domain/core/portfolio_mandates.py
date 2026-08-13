from __future__ import annotations

import json

from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

from database.models.portfolio_mandates import StrategyMandate


def test_jsonb_fields_are_mapped_columns() -> None:
    expected = {
        StrategyMandate: {"config"},
    }

    for model, columns in expected.items():
        assert columns <= set(model.__table__.columns.keys())


def test_jsonb_dialect_round_trip_preserves_nested_payload() -> None:
    dialect = postgresql.dialect()
    bind = JSONB().bind_processor(dialect)
    result = JSONB().result_processor(dialect, None)
    payload = {"claims": [{"verified": True}], "value": "1234567890.12"}

    encoded = bind(payload) if bind else json.dumps(payload)
    decoded = result(encoded) if result else json.loads(encoded)

    assert decoded == payload
