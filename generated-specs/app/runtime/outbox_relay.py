"""Outbox relay and RabbitMQ topology."""
from __future__ import annotations

from dataclasses import dataclass

import pika
import psycopg
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from .schema import schema_name
from .telemetry import context_from, traceparent_of, tracer


@dataclass(frozen=True)
class Topology:
    exchange: str
    queue: str
    dlx: str
    dlq: str


def topology(prefix: str = "autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework") -> Topology:
    return Topology(f"{prefix}.events", f"{prefix}.consumer", f"{prefix}.dlx", f"{prefix}.dlq")


DEFAULT_TOPOLOGY = Topology("autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework.events", "autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework.consumer", "autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework.dlx", "autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework.dlq")


def declare_topology(channel, t: Topology = DEFAULT_TOPOLOGY) -> None:
    """Topic exchange -> consumer queue, which dead-letters rejected messages to a fanout DLX -> DLQ."""
    channel.exchange_declare(exchange=t.exchange, exchange_type="topic", durable=True)
    channel.exchange_declare(exchange=t.dlx, exchange_type="fanout", durable=True)
    channel.queue_declare(queue=t.dlq, durable=True)
    channel.queue_bind(queue=t.dlq, exchange=t.dlx, routing_key="")
    channel.queue_declare(queue=t.queue, durable=True, arguments={"x-dead-letter-exchange": t.dlx})
    channel.queue_bind(queue=t.queue, exchange=t.exchange, routing_key="#")


class OutboxRelay:
    """Publishes pending outbox rows. Rows are claimed with FOR UPDATE SKIP LOCKED and a lease, so
    concurrent relays never publish the same row; publisher confirms guarantee delivery to the
    broker before a row is marked published. Use one relay (and channel) per thread."""

    def __init__(self, dsn: str, channel, exchange: str = DEFAULT_TOPOLOGY.exchange, schema: str = "public",
                 lease_seconds: int = 30, max_attempts: int = 5) -> None:
        self.dsn = dsn
        self.channel = channel
        self.channel.confirm_delivery()
        self.exchange = exchange
        self.s = schema_name(schema)
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts

    def publish_batch(self, worker_id: str, limit: int = 50) -> int:
        s = self.s
        with psycopg.connect(self.dsn, autocommit=True) as conn:
            rows = conn.execute(
                f"UPDATE {s}.ghk_outbox SET claimed_by = %s, claimed_until = now() + make_interval(secs => %s), attempts = attempts + 1 "
                f"WHERE id IN (SELECT id FROM {s}.ghk_outbox WHERE published_at IS NULL AND failed_at IS NULL "
                f"AND (claimed_until IS NULL OR claimed_until < now()) ORDER BY created_at LIMIT %s FOR UPDATE SKIP LOCKED) "
                f"RETURNING id, tenant_id, aggregate_id, event_type, payload, traceparent",
                (worker_id, self.lease_seconds, limit)).fetchall()
            published = 0
            for (id_, tenant_id, _aggregate_id, event_type, payload, traceparent) in rows:
                parent = context_from(traceparent)
                with tracer().start_as_current_span(f"{self.exchange} publish", context=parent, kind=SpanKind.PRODUCER,
                                                    attributes={"messaging.system": "rabbitmq", "messaging.destination.name": self.exchange,
                                                                "messaging.message.id": id_, "tenant.id": tenant_id}) as span:
                    try:
                        headers = {"tenant_id": tenant_id}
                        tp = traceparent_of(trace.set_span_in_context(span, parent))
                        if tp:
                            headers["traceparent"] = tp
                        self.channel.basic_publish(
                            exchange=self.exchange, routing_key=event_type, body=payload.encode("utf-8"),
                            properties=pika.BasicProperties(message_id=id_, delivery_mode=2, content_type="application/json",
                                                            type=event_type, headers=headers),
                            mandatory=False)
                        conn.execute(f"UPDATE {s}.ghk_outbox SET published_at = now(), claimed_until = NULL WHERE id = %s AND claimed_by = %s", (id_, worker_id))
                        published += 1
                    except Exception as err:  # broker unavailable / nacked: release the lease, retry later
                        span.record_exception(err)
                        span.set_status(Status(StatusCode.ERROR))
                        conn.execute(
                            f"UPDATE {s}.ghk_outbox SET claimed_until = NULL, last_error = %s, "
                            f"failed_at = CASE WHEN attempts >= %s THEN now() ELSE NULL END WHERE id = %s",
                            (str(err), self.max_attempts, id_))
            return published
