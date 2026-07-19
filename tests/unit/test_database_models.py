from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

from database.models import AgentAssessment, AgentDefinition, AgentRun, Document, FinancialStatement


def test_jsonb_fields_are_mapped_columns() -> None:
    expected = {
        AgentDefinition: {"model_config"},
        AgentRun: {"input_data", "output_data"},
        AgentAssessment: {"claims", "risks", "assumptions", "data_gaps"},
        Document: {"canonical_data"},
        FinancialStatement: {"line_items", "raw_data"},
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


def test_jsonb_filter_compiles_to_postgresql_operator() -> None:
    statement = select(AgentRun.id).where(AgentRun.input_data.contains({"issuer_id": "issuer-1"}))

    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert "@>" in compiled
