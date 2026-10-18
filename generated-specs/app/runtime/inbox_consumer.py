"""Idempotent consumer with dead-lettering."""
from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict

import psycopg
from opentelemetry.trace import SpanKind, Status, StatusCode

from .broker import Delivery, EventSubscription
from .schema import schema_name
from .telemetry import context_from, tracer

Handler = Callable[[Dict[str, Any], Dict[str, Any]], None]


class InboxConsumer:
    """The message id is recorded in ghk_inbox in the same transaction as the handler, so
    redeliveries are acknowledged without running the handler twice. A handler error dead-letters
    the message (RabbitMQ DLX, Pub/Sub / Service Bus dead-letter topic): it is not redelivered."""

    def __init__(self, dsn: str, subscription: EventSubscription, consumer_name: str, handler: Handler, schema: str = "public") -> None:
        self.dsn = dsn
        self.subscription = subscription
        self.consumer_name = consumer_name
        self.handler = handler
        self.s = schema_name(schema)

    def drain(self, idle_seconds: float = 1.0) -> int:
        """Processes messages until the source stays idle for idle_seconds. Returns how many were processed."""
        processed = 0
        idle_since = time.monotonic()
        while time.monotonic() - idle_since < idle_seconds:
            delivery = self.subscription.poll()
            if delivery is None:
                time.sleep(0.05)
                continue
            self.process(delivery)
            processed += 1
            idle_since = time.monotonic()
        return processed

    def process(self, delivery: Delivery) -> None:
        message = delivery.message
        source = self.subscription.source
        with tracer().start_as_current_span(f"{source} process", context=context_from(message.traceparent), kind=SpanKind.CONSUMER,
                                            attributes={"messaging.system": self.subscription.system, "messaging.destination.name": source,
                                                        "messaging.message.id": message.message_id}) as span:
            try:
                with psycopg.connect(self.dsn) as conn:
                    first = conn.execute(f"INSERT INTO {self.s}.ghk_inbox (consumer, message_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                                         (self.consumer_name, message.message_id))
                    if first.rowcount == 1:
                        self.handler(json.loads(message.body), {"message_id": message.message_id, "tenant_id": message.tenant_id,
                                                                "event_type": message.event_type, "connection": conn})
                    conn.commit()
                delivery.ack()
            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR))
                delivery.dead_letter()
