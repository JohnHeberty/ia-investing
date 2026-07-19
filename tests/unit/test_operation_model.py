from database.models.operations import Operation


def test_operation_has_idempotency_and_state_constraints() -> None:
    constraints = {constraint.name for constraint in Operation.__table__.constraints}

    assert "uq_operations_type_idempotency_key" in constraints
    assert "ck_operations_operation_state" in constraints
    assert Operation.request_data.nullable is False
