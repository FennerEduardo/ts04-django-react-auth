"""HTTP contract of the application layer against PostgreSQL (needs DATABASE_URL)."""
import os
import uuid

import psycopg
import pytest

from app.auth import TENANT_CLAIM, sign_jwt
from app.runtime.schema import migrate

pytestmark = pytest.mark.integration
SECRET = "integration-test-secret-with-32-chars!"
DSN = os.environ.get("DATABASE_URL", "")


@pytest.fixture
def client(monkeypatch):
    if not DSN:
        pytest.skip("DATABASE_URL is not set")
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from django.test import Client

    from app import views

    views.command_service.cache_clear()
    return Client()


def test_runs_a_command_into_the_outbox_for_the_token_tenant_idempotently(client):
    migrate(DSN)
    tenant = f"tenant-{uuid.uuid4()}"
    aggregate_id = str(uuid.uuid4())
    headers = {"authorization": f"Bearer {sign_jwt({TENANT_CLAIM: tenant}, SECRET)}", "idempotency-key": str(uuid.uuid4()), "x-tenant-id": "someone-else"}
    url = f"/api/v1/autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework/{aggregate_id}/process_autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework"
    first = client.post(url, {}, content_type="application/json", **{f"HTTP_{k.upper().replace('-', '_')}": v for k, v in headers.items()})
    assert first.status_code == 202
    replay = client.post(url, {}, content_type="application/json", **{f"HTTP_{k.upper().replace('-', '_')}": v for k, v in headers.items()})
    assert replay.status_code == 200
    assert replay.json()["status"] == "replayed"
    with psycopg.connect(DSN) as conn:
        rows = conn.execute("SELECT tenant_id FROM ghk_outbox WHERE aggregate_id = %s", (aggregate_id,)).fetchall()
    assert rows == [(tenant,)]


def test_rejects_a_request_with_only_x_tenant_id(client):
    url = f"/api/v1/autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework/{uuid.uuid4()}/process_autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework"
    headers = {"x-tenant-id": "acme"}
    assert (client.post(url, {}, content_type="application/json", **{f"HTTP_{k.upper().replace('-', '_')}": v for k, v in headers.items()})).status_code == 401
