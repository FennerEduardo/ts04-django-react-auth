import pytest

from app.models import OutboxMessage


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.django_db
def test_executes_a_command_and_stores_the_event_in_the_outbox(client):
    res = client.post("/api/v1/autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework/agg-api/process_autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework", {"source": "api-test"}, content_type="application/json")
    assert res.status_code == 201
    assert res.json() == {"type": "ProcessAutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkCompleted", "aggregateId": "agg-api", "version": 1}
    stored = OutboxMessage.objects.get(aggregate_id="agg-api")
    assert stored.event_type == "ProcessAutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkCompleted"
    assert stored.processed_on is None


def test_unknown_command_returns_404(client):
    assert client.post("/api/v1/autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework/agg-api/does_not_exist").status_code == 404
