"""HTTP contract with a fake command service (no database)."""
import pytest

from app import views
from app.auth import TENANT_CLAIM, sign_jwt
from app.domain import DomainValidationError
from app.runtime.command_service import CommandResult

SECRET = "unit-test-secret-with-at-least-32-chars"


class FakeCommands:
    def __init__(self):
        self.calls = []

    def handle(self, tenant_id, aggregate_id, command, payload=None, idempotency_key=None, traceparent=None, aggregate_type=None):
        self.calls.append((tenant_id, aggregate_id, command, payload))
        if command == "does_not_exist":
            raise DomainValidationError(f"Unknown command {command}")
        return CommandResult("replayed" if idempotency_key == "seen" else "created", aggregate_id, "ProcessAutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkCompleted", 1)


@pytest.fixture
def fake(monkeypatch):
    commands = FakeCommands()
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setattr(views, "command_service", lambda: commands)
    return commands


def bearer(claims, secret=SECRET):
    return f"Bearer {sign_jwt(claims, secret)}"


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_runs_a_command_for_the_token_tenant(client, fake):
    res = client.post("/api/v1/autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework/agg-api/process_autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework", {"source": "api-test"}, content_type="application/json",
                      HTTP_AUTHORIZATION=bearer({TENANT_CLAIM: "acme"}), HTTP_X_TENANT_ID="someone-else")
    assert res.status_code == 202
    assert fake.calls[-1] == ("acme", "agg-api", "process_autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework", {"source": "api-test"})


def test_idempotent_replay_returns_200(client, fake):
    res = client.post("/api/v1/autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework/agg-api/process_autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework", content_type="application/json",
                      HTTP_AUTHORIZATION=bearer({TENANT_CLAIM: "acme"}), HTTP_IDEMPOTENCY_KEY="seen")
    assert res.status_code == 200


def test_rejects_missing_or_invalid_tokens_and_x_tenant_id(client, fake):
    url = "/api/v1/autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework/agg-api/process_autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework"
    assert client.post(url).status_code == 401
    assert client.post(url, HTTP_X_TENANT_ID="acme").status_code == 401
    assert client.post(url, HTTP_AUTHORIZATION=bearer({"sub": "u1"})).status_code == 401
    assert client.post(url, HTTP_AUTHORIZATION=bearer({TENANT_CLAIM: "acme"}, "wrong")).status_code == 401


def test_domain_validation_error_is_422(client, fake):
    assert client.post("/api/v1/autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework/agg-api/does_not_exist", HTTP_AUTHORIZATION=bearer({TENANT_CLAIM: "acme"})).status_code == 422
