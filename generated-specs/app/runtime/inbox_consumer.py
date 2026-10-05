"""Idempotent consumer with dead-lettering."""
from __future__ import annotations

import json
from typing import Any, Callable, Dict

import psycopg
from opentelemetry.trace import SpanKind, Status, StatusCode

from .schema import schema_name
from .telemetry import context_from, tracer

Handler = Callable[[Dict[str, Any], Dict[str, Any]], None]


class InboxConsumer:
    """The message id is recorded in ghk_inbox in the same transaction as the handler, so
    redeliveries are acknowledged without running the handler twice. A handler error rejects the
    message without requeue, so RabbitMQ dead-letters it to the DLQ."""

    def __init__(self, dsn: str, channel, queue: str, consumer_name: str, handler: Handler, schema: str = "public") -> None:
        self.dsn = dsn
        self.channel = channel
        self.queue = queue
        self.consumer_name = consumer_name
        self.handler = handler
        self.s = schema_name(schema)

    def drain(self, idle_seconds: float = 1.0) -> int:
        """Processes messages until the queue stays idle for idle_seconds. Returns how many were processed."""
        processed = 0
        for method, properties, body in self.channel.consume(self.queue, inactivity_timeout=idle_seconds):
            if method is None:
                break
            self.on_message(method, properties, body)
            processed += 1
        self.channel.cancel()
        return processed

    def on_message(self, method, properties, body: bytes) -> None:
        headers = properties.headers or {}
        message_id = str(properties.message_id)
        with tracer().start_as_current_span(f"{self.queue} process", context=context_from(headers.get("traceparent")), kind=SpanKind.CONSUMER,
                                            attributes={"messaging.system": "rabbitmq", "messaging.destination.name": self.queue,
                                                        "messaging.message.id": message_id}) as span:
            try:
                with psycopg.connect(self.dsn) as conn:
                    first = conn.execute(f"INSERT INTO {self.s}.ghk_inbox (consumer, message_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                                         (self.consumer_name, message_id))
                    if first.rowcount == 1:
                        self.handler(json.loads(body), {"message_id": message_id, "tenant_id": headers.get("tenant_id"),
                                                        "event_type": properties.type, "connection": conn})
                    conn.commit()
                self.channel.basic_ack(method.delivery_tag)
            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR))
                self.channel.basic_nack(method.delivery_tag, requeue=False)
