"""python manage.py outbox_relay: publishes the outbox to the configured broker (DATABASE_URL; AMQP_URL, PUBSUB_* or SERVICEBUS_*)."""
import os
import signal
import threading

from django.core.management.base import BaseCommand

from app.runtime.otel import start_telemetry
from app.worker import start_outbox_relay


class Command(BaseCommand):
    help = "Publish the transactional outbox to the event broker until interrupted."

    def handle(self, *args, **options):
        start_telemetry()
        stop = start_outbox_relay(os.environ["DATABASE_URL"])
        done = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: done.set())
        try:
            done.wait()
        except KeyboardInterrupt:
            pass
        stop()
