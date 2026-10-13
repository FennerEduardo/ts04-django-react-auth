"""python manage.py outbox_relay: publishes the outbox to RabbitMQ (DATABASE_URL, AMQP_URL)."""
import os
import signal
import threading

from django.core.management.base import BaseCommand

from app.worker import start_outbox_relay


class Command(BaseCommand):
    help = "Publish the transactional outbox to RabbitMQ until interrupted."

    def handle(self, *args, **options):
        stop = start_outbox_relay(os.environ["DATABASE_URL"], os.environ["AMQP_URL"])
        done = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: done.set())
        try:
            done.wait()
        except KeyboardInterrupt:
            pass
        stop()
