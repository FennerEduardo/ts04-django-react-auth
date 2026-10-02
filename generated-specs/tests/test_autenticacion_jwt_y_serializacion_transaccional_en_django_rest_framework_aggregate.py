import pytest

from app.domain import (
    DomainValidationError,
    AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkAggregate,
    AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkCommand,
    AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkEventType,
    AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkState,
)


def test_starts_in_the_initial_state_with_no_events():
    aggregate = AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkAggregate("agg-1")
    assert aggregate.state == AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkState.PENDING
    assert aggregate.version == 0
    assert aggregate.pending_events == []


def test_rejects_an_aggregate_without_id():
    with pytest.raises(DomainValidationError):
        AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkAggregate("")


def test_process_autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework_records_event_and_bumps_the_version():
    aggregate = AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkAggregate("agg-1")
    event = aggregate.process_autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework(AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkCommand("agg-1", {"source": "test"}))
    assert event.type == AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkEventType.ProcessAutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkCompleted
    assert event.version == 1
    assert aggregate.version == 1
    assert aggregate.pending_events == [event]


def test_process_autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework_rejects_a_command_without_id():
    aggregate = AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkAggregate("agg-1")
    with pytest.raises(DomainValidationError):
        aggregate.process_autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework(AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkCommand(""))
    assert aggregate.pending_events == []
