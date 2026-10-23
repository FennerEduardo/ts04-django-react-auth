"""Outbox relay worker: publishes the outbox every 1000 ms through the configured broker
(app/runtime/broker.py: GHK_BROKER, AMQP_URL, PUBSUB_*, SERVICEBUS_*)."""
from __future__ import annotations

import logging
import os
import threading
import uuid
from typing import Callable

from app.runtime.broker import DEFAULT_TOPOLOGY, connect_broker
from app.runtime.outbox_relay import OutboxRelay

log = logging.getLogger(__name__)


def start_outbox_relay(dsn: str, interval: float = 1) -> Callable[[], None]:
    """Starts the relay thread; returns a function that stops it."""
    stop = threading.Event()
    worker_id = f"autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework-{uuid.uuid4()}"

    def run() -> None:
        while not stop.is_set():
            try:
                broker = connect_broker()
                # GHK_DECLARE_TOPOLOGY=false when infrastructure as code owns the topology (least-privilege credentials).
                if os.environ.get("GHK_DECLARE_TOPOLOGY") != "false":
                    broker.declare(DEFAULT_TOPOLOGY)
                publisher = broker.publisher(DEFAULT_TOPOLOGY.exchange)
                try:
                    relay = OutboxRelay(dsn, publisher)
                    while not stop.is_set():
                        relay.publish_batch(worker_id)
                        stop.wait(interval)
                finally:
                    publisher.close()
                    broker.close()
            except Exception:  # broker or database unavailable: retry
                log.exception("outbox relay failed; retrying")
                stop.wait(5)

    threading.Thread(target=run, name="outbox-relay", daemon=True).start()
    return stop.set
