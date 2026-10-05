"""Executes commands in one transaction: idempotency claim, aggregate load (FOR UPDATE),
domain logic, aggregate save and outbox insert. A domain error rolls everything back."""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, Optional

import psycopg
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from app.domain import AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkAggregate, AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkCommand, AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkDomainEvent, AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkState, DomainValidationError
from .schema import schema_name
from .telemetry import context_from, traceparent_of, tracer

AGGREGATE_TYPE = "AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFramework"

COMMANDS: Dict[str, Callable[[AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkAggregate, AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkCommand], AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkDomainEvent]] = {
    "process_autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework": lambda a, c: a.process_autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework(c),
}


@dataclass
class CommandResult:
    status: str
    aggregate_id: str
    event_type: Optional[str] = None
    version: Optional[int] = None


def _event_json(event: AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkDomainEvent) -> str:
    return json.dumps({
        "type": event.type.value,
        "aggregateId": event.aggregate_id,
        "version": event.version,
        "occurredOn": event.occurred_on.isoformat(),
        "payload": event.payload,
    })


class CommandService:
    def __init__(self, dsn: str, schema: str = "public") -> None:
        self.dsn = dsn
        self.s = schema_name(schema)

    def handle(self, tenant_id: str, aggregate_id: str, command: str, payload: Optional[Dict[str, Any]] = None,
               idempotency_key: Optional[str] = None, traceparent: Optional[str] = None) -> CommandResult:
        if not tenant_id:
            raise DomainValidationError("tenant_id is required")
        parent = context_from(traceparent)
        with tracer().start_as_current_span(f"AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFramework.{command}", context=parent, kind=SpanKind.INTERNAL,
                                            attributes={"tenant.id": tenant_id, "aggregate.id": aggregate_id}) as span:
            try:
                return self._handle(tenant_id, aggregate_id, command, payload or {}, idempotency_key, trace.set_span_in_context(span, parent))
            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise

    def _handle(self, tenant_id, aggregate_id, command, payload, key, ctx) -> CommandResult:
        s = self.s
        with psycopg.connect(self.dsn) as conn:  # one transaction; rolled back on exception
            if key:
                claimed = conn.execute(f"INSERT INTO {s}.ghk_idempotency (tenant_id, key, status) VALUES (%s, %s, 'PROCESSING') ON CONFLICT DO NOTHING", (tenant_id, key))
                if claimed.rowcount == 0:
                    row = conn.execute(f"SELECT status, response FROM {s}.ghk_idempotency WHERE tenant_id = %s AND key = %s", (tenant_id, key)).fetchone()
                    conn.commit()
                    if row and row[0] == "COMPLETED":
                        return CommandResult(**{**json.loads(row[1]), "status": "replayed"})
                    return CommandResult("in-progress", aggregate_id)
            row = conn.execute(f"SELECT state, version FROM {s}.ghk_aggregates WHERE tenant_id = %s AND aggregate_type = %s AND id = %s FOR UPDATE",
                               (tenant_id, AGGREGATE_TYPE, aggregate_id)).fetchone()
            aggregate = AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkAggregate.restore(aggregate_id, AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkState(row[0]), int(row[1])) if row else AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkAggregate(aggregate_id)
            handler = COMMANDS.get(command)
            if handler is None:
                raise DomainValidationError(f"Unknown command {command}")
            event = handler(aggregate, AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkCommand(aggregate_id, payload))
            conn.execute(
                f"INSERT INTO {s}.ghk_aggregates (tenant_id, aggregate_type, id, state, version) VALUES (%s, %s, %s, %s, %s) "
                f"ON CONFLICT (tenant_id, aggregate_type, id) DO UPDATE SET state = EXCLUDED.state, version = EXCLUDED.version, updated_at = now()",
                (tenant_id, AGGREGATE_TYPE, aggregate_id, aggregate.state.value, aggregate.version))
            conn.execute(
                f"INSERT INTO {s}.ghk_outbox (id, tenant_id, aggregate_id, event_type, payload, traceparent) VALUES (%s, %s, %s, %s, %s, %s)",
                (str(uuid.uuid4()), tenant_id, aggregate_id, event.type.value, _event_json(event), traceparent_of(ctx)))
            result = CommandResult("created", aggregate_id, event.type.value, event.version)
            if key:
                conn.execute(f"UPDATE {s}.ghk_idempotency SET status = 'COMPLETED', response = %s WHERE tenant_id = %s AND key = %s",
                             (json.dumps(asdict(result)), tenant_id, key))
            conn.commit()
            return result

    def load(self, tenant_id: str, aggregate_id: str) -> Optional[Dict[str, Any]]:
        """The aggregate as tenant `tenant_id` sees it (None for other tenants' aggregates)."""
        with psycopg.connect(self.dsn) as conn:
            row = conn.execute(f"SELECT state, version FROM {self.s}.ghk_aggregates WHERE tenant_id = %s AND aggregate_type = %s AND id = %s",
                               (tenant_id, AGGREGATE_TYPE, aggregate_id)).fetchone()
        return {"state": row[0], "version": int(row[1])} if row else None
