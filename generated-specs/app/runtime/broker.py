"""The event broker behind the outbox relay and the inbox consumer, chosen at run time so one image runs on
any cloud: GHK_BROKER=rabbitmq (AMQP_URL), pubsub (PUBSUB_PROJECT_ID or GOOGLE_CLOUD_PROJECT; PUBSUB_EMULATOR_HOST)
or servicebus (SERVICEBUS_NAMESPACE or SERVICEBUS_CONNECTION_STRING). Without GHK_BROKER the configured
variables decide, then stack.messaging."""
from __future__ import annotations

import base64
import json
import os
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import pika


@dataclass(frozen=True)
class Topology:
    """Publish to exchange (topic), consume from queue (subscription); dead letters go to dlx, read from dlq."""
    exchange: str
    queue: str
    dlx: str
    dlq: str


def topology(prefix: str = "django-react-auth") -> Topology:
    return Topology(f"{prefix}.events", f"{prefix}.consumer", f"{prefix}.dlx", f"{prefix}.dlq")


DEFAULT_TOPOLOGY = Topology("django-react-auth.events", "django-react-auth.consumer", "django-react-auth.dlx", "django-react-auth.dlq")

# Broker of the generated configuration (stack.messaging).
DEFAULT_BROKER = "rabbitmq"


@dataclass(frozen=True)
class BrokerMessage:
    """A domain event on the wire, independent of the broker."""
    message_id: str
    event_type: Optional[str]
    tenant_id: Optional[str]
    traceparent: Optional[str]
    body: bytes


@dataclass
class Delivery:
    """A received message: ack() once processed; dead_letter() moves it to the DLQ (it is not redelivered)."""
    message: BrokerMessage
    ack: Callable[[], None]
    dead_letter: Callable[[], None]


class EventPublisher:
    """Publishes to one destination; publish returns only once the broker has durably accepted the message."""
    system = ""
    destination = ""

    def publish(self, message: BrokerMessage) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass


class EventSubscription:
    """Pulls messages from one queue / subscription."""
    system = ""
    source = ""

    def poll(self) -> Optional[Delivery]:
        """The next waiting message, or None when there is none."""
        raise NotImplementedError

    def close(self) -> None:
        pass


class Broker:
    system = ""
    # False when topics cannot be created at run time (Service Bus emulator: fixed Config.json).
    dynamic_topology = True

    def declare(self, t: Topology) -> None:
        """Creates the topology if missing (idempotent); in production it usually comes from infrastructure as code."""
        raise NotImplementedError

    def publisher(self, destination: str) -> EventPublisher:
        raise NotImplementedError

    def subscribe(self, source: str, t: Topology) -> EventSubscription:
        """t: where dead-lettered messages go."""
        raise NotImplementedError

    def close(self) -> None:
        pass


def broker_kind(env=os.environ) -> str:
    if env.get("GHK_BROKER", "").strip():
        return env["GHK_BROKER"].strip().lower()
    if env.get("AMQP_URL"):
        return "rabbitmq"
    if env.get("PUBSUB_PROJECT_ID") or env.get("PUBSUB_EMULATOR_HOST"):
        return "pubsub"
    if env.get("SERVICEBUS_CONNECTION_STRING") or env.get("SERVICEBUS_NAMESPACE"):
        return "servicebus"
    if env.get("KAFKA_BOOTSTRAP_SERVERS"):
        return "kafka"
    return DEFAULT_BROKER


def broker_configured(env=os.environ) -> bool:
    """Whether the variables of the selected broker are set."""
    kind = broker_kind(env)
    if kind == "pubsub":
        return bool(env.get("PUBSUB_PROJECT_ID") or env.get("GOOGLE_CLOUD_PROJECT"))
    if kind == "servicebus":
        return bool(env.get("SERVICEBUS_CONNECTION_STRING") or env.get("SERVICEBUS_NAMESPACE"))
    if kind == "kafka":
        return bool(env.get("KAFKA_BOOTSTRAP_SERVERS"))
    return bool(env.get("AMQP_URL"))


def connect_broker(env=os.environ) -> Broker:
    kind = broker_kind(env)
    if kind == "rabbitmq":
        if not env.get("AMQP_URL"):
            raise RuntimeError("AMQP_URL is not set (amqp://user:password@host:5672)")
        return RabbitMqBroker(env["AMQP_URL"])
    if kind == "pubsub":
        return PubSubBroker.from_env(env)
    if kind == "servicebus":
        raise RuntimeError('The Azure Service Bus adapter is not generated: set stack.messaging to "servicebus" and regenerate')
    if kind == "kafka":
        raise RuntimeError('The Kafka adapter is not generated: set stack.messaging to "kafka" and regenerate')
    raise RuntimeError(f"Unsupported GHK_BROKER: {kind} (rabbitmq, pubsub, servicebus, kafka)")


class RabbitMqBroker(Broker):
    """RabbitMQ 0-9-1: topic exchange, publisher confirms, dead-lettering through the queue's DLX.
    pika's BlockingConnection is not thread-safe, so each publisher / subscription has its own connection."""
    system = "rabbitmq"

    def __init__(self, url: str) -> None:
        self.url = url

    def _connect(self):
        # A busy host can delay the AMQP handshake: retry before failing.
        for attempt in range(1, 6):
            try:
                return pika.BlockingConnection(pika.URLParameters(self.url))
            except pika.exceptions.AMQPConnectionError:
                if attempt == 5:
                    raise
                time.sleep(2 * attempt)

    def declare(self, t: Topology) -> None:
        connection = self._connect()
        try:
            channel = connection.channel()
            channel.exchange_declare(exchange=t.exchange, exchange_type="topic", durable=True)
            channel.exchange_declare(exchange=t.dlx, exchange_type="fanout", durable=True)
            channel.queue_declare(queue=t.dlq, durable=True)
            channel.queue_bind(queue=t.dlq, exchange=t.dlx, routing_key="")
            channel.queue_declare(queue=t.queue, durable=True, arguments={"x-dead-letter-exchange": t.dlx})
            channel.queue_bind(queue=t.queue, exchange=t.exchange, routing_key="#")
        finally:
            connection.close()

    def publisher(self, exchange: str) -> EventPublisher:
        return _RabbitPublisher(self._connect(), exchange)

    def subscribe(self, queue: str, t: Topology) -> EventSubscription:
        return _RabbitSubscription(self._connect(), queue)


class _RabbitPublisher(EventPublisher):
    system = "rabbitmq"

    def __init__(self, connection, exchange: str) -> None:
        self.connection = connection
        self.channel = connection.channel()
        self.channel.confirm_delivery()
        self.destination = exchange

    def publish(self, m: BrokerMessage) -> None:
        headers = {}
        if m.tenant_id:
            headers["tenant_id"] = m.tenant_id
        if m.traceparent:
            headers["traceparent"] = m.traceparent
        # With confirms on, basic_publish raises if the broker nacks the message.
        self.channel.basic_publish(exchange=self.destination, routing_key=m.event_type or "", body=m.body,
                                   properties=pika.BasicProperties(message_id=m.message_id, delivery_mode=2, content_type="application/json",
                                                                   type=m.event_type, headers=headers))

    def close(self) -> None:
        if self.connection.is_open:
            self.connection.close()


class _RabbitSubscription(EventSubscription):
    system = "rabbitmq"

    def __init__(self, connection, queue: str) -> None:
        self.connection = connection
        self.channel = connection.channel()
        self.source = queue

    def poll(self) -> Optional[Delivery]:
        method, properties, body = self.channel.basic_get(self.source, auto_ack=False)
        if method is None:
            return None
        headers = properties.headers or {}
        text = lambda v: None if v is None else (v.decode() if isinstance(v, bytes) else str(v))
        message = BrokerMessage(str(properties.message_id), properties.type, text(headers.get("tenant_id")), text(headers.get("traceparent")), body)
        tag = method.delivery_tag
        # Rejected without requeue: RabbitMQ dead-letters it through the queue's DLX.
        return Delivery(message, lambda: self.channel.basic_ack(tag), lambda: self.channel.basic_nack(tag, requeue=False))

    def close(self) -> None:
        if self.connection.is_open:
            self.connection.close()


_METADATA_TOKEN = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"


class PubSubBroker(Broker):
    """Google Cloud Pub/Sub over its REST API (no client library): topics for the exchange and the DLX, pull
    subscriptions for the queue and the DLQ. publish returns once Pub/Sub has stored the message. A failed message
    is dead-lettered by the consumer: published to the DLX topic, then acknowledged.
    Auth: none against the emulator (PUBSUB_EMULATOR_HOST); otherwise GOOGLE_OAUTH_ACCESS_TOKEN or the metadata-server
    token of the workload's service account (Cloud Run, GKE workload identity)."""
    system = "gcp_pubsub"

    def __init__(self, project: str, emulator_host: Optional[str] = None) -> None:
        self.project = project
        self.emulator = bool(emulator_host)
        self.root = (f"http://{emulator_host}" if self.emulator else "https://pubsub.googleapis.com") + f"/v1/projects/{project}"
        self._token: Optional[str] = None
        self._token_expires_at = 0.0
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls, env=os.environ) -> "PubSubBroker":
        project = env.get("PUBSUB_PROJECT_ID") or env.get("GOOGLE_CLOUD_PROJECT")
        if not project:
            raise RuntimeError("PUBSUB_PROJECT_ID (or GOOGLE_CLOUD_PROJECT) is not set")
        return cls(project, env.get("PUBSUB_EMULATOR_HOST"))

    def _bearer(self) -> Optional[str]:
        if self.emulator:
            return None
        if os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN"):
            return os.environ["GOOGLE_OAUTH_ACCESS_TOKEN"]
        with self._lock:
            if not self._token or time.time() > self._token_expires_at:
                req = urllib.request.Request(_METADATA_TOKEN, headers={"Metadata-Flavor": "Google"})
                with urllib.request.urlopen(req, timeout=5) as res:
                    body = json.loads(res.read())
                self._token = body["access_token"]
                self._token_expires_at = time.time() + body["expires_in"] - 60
            return self._token

    def _call(self, method: str, path: str, body: Any = None, accepted=()) -> Optional[Dict[str, Any]]:
        """Calls the API; a status listed in accepted returns None instead of failing."""
        headers = {"Content-Type": "application/json"}
        bearer = self._bearer()
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.root + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                text = res.read()
                return json.loads(text) if text else {}
        except urllib.error.HTTPError as err:
            if err.code in accepted:
                return None
            raise RuntimeError(f"Pub/Sub {method} {path} failed: {err.code} {err.read().decode(errors='replace')}") from err

    def declare(self, t: Topology) -> None:
        # 409: it already exists (created earlier or by infrastructure as code).
        self._call("PUT", f"/topics/{t.exchange}", {}, accepted=(409,))
        self._call("PUT", f"/topics/{t.dlx}", {}, accepted=(409,))
        self._call("PUT", f"/subscriptions/{t.queue}", {"topic": f"projects/{self.project}/topics/{t.exchange}", "ackDeadlineSeconds": 60}, accepted=(409,))
        self._call("PUT", f"/subscriptions/{t.dlq}", {"topic": f"projects/{self.project}/topics/{t.dlx}", "ackDeadlineSeconds": 60}, accepted=(409,))

    def publish_to(self, topic: str, m: BrokerMessage) -> None:
        attributes = {"ghk_message_id": m.message_id}
        if m.event_type:
            attributes["event_type"] = m.event_type
        if m.tenant_id:
            attributes["tenant_id"] = m.tenant_id
        if m.traceparent:
            attributes["traceparent"] = m.traceparent
        res = self._call("POST", f"/topics/{topic}:publish", {"messages": [{"data": base64.b64encode(m.body).decode(), "attributes": attributes}]})
        if not res or len(res.get("messageIds", [])) != 1:
            raise RuntimeError(f"Pub/Sub did not accept message {m.message_id}")

    def publisher(self, topic: str) -> EventPublisher:
        return _PubSubPublisher(self, topic)

    def subscribe(self, subscription: str, t: Topology) -> EventSubscription:
        return _PubSubSubscription(self, subscription, t)


class _PubSubPublisher(EventPublisher):
    system = "gcp_pubsub"

    def __init__(self, broker: PubSubBroker, topic: str) -> None:
        self.broker = broker
        self.destination = topic

    def publish(self, m: BrokerMessage) -> None:
        self.broker.publish_to(self.destination, m)


class _PubSubSubscription(EventSubscription):
    system = "gcp_pubsub"

    def __init__(self, broker: PubSubBroker, subscription: str, t: Topology) -> None:
        self.broker = broker
        self.source = subscription
        self.t = t

    def poll(self) -> Optional[Delivery]:
        res = self.broker._call("POST", f"/subscriptions/{self.source}:pull", {"maxMessages": 1, "returnImmediately": True}) or {}
        received = res.get("receivedMessages") or []
        if not received:
            return None
        ack_id = received[0]["ackId"]
        msg = received[0]["message"]
        attrs = msg.get("attributes") or {}
        message = BrokerMessage(attrs.get("ghk_message_id") or msg["messageId"], attrs.get("event_type"), attrs.get("tenant_id"),
                                attrs.get("traceparent"), base64.b64decode(msg.get("data", "")))

        def ack() -> None:
            self.broker._call("POST", f"/subscriptions/{self.source}:acknowledge", {"ackIds": [ack_id]})

        def dead_letter() -> None:
            self.broker.publish_to(self.t.dlx, message)
            ack()

        return Delivery(message, ack, dead_letter)
