"""Outbox relay worker: publishes the outbox every 1000 ms while AMQP_URL is set."""
from __future__ import annotations

import logging
import threading
import uuid
from typing import Callable

import pika

from app.runtime.outbox_relay import DEFAULT_TOPOLOGY, OutboxRelay, declare_topology

log = logging.getLogger(__name__)


def start_outbox_relay(dsn: str, amqp_url: str, interval: float = 1) -> Callable[[], None]:
    """Starts the relay thread; returns a function that stops it."""
    stop = threading.Event()
    worker_id = f"autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework-{uuid.uuid4()}"

    def run() -> None:
        while not stop.is_set():
            try:
                connection = pika.BlockingConnection(pika.URLParameters(amqp_url))
                try:
                    channel = connection.channel()
                    declare_topology(channel)
                    relay = OutboxRelay(dsn, channel, DEFAULT_TOPOLOGY.exchange)
                    while not stop.is_set():
                        relay.publish_batch(worker_id)
                        stop.wait(interval)
                finally:
                    if connection.is_open:
                        connection.close()
            except Exception:  # broker or database unavailable: retry
                log.exception("outbox relay failed; retrying")
                stop.wait(5)

    threading.Thread(target=run, name="outbox-relay", daemon=True).start()
    return stop.set
