"""Runtime integration tests (docs/RUNTIME-KERNEL.md, IT1-IT7) against PostgreSQL and the selected broker
(GHK_BROKER: rabbitmq with AMQP_URL, pubsub with PUBSUB_PROJECT_ID [+ PUBSUB_EMULATOR_HOST], servicebus).
Requires DATABASE_URL. Run with: pytest -m integration"""
import os
import threading
import time
import uuid

import psycopg
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind

from app.domain import DomainValidationError
from app.runtime import (BrokerMessage, CommandService, InboxConsumer, OutboxRelay, SagaOrchestrator, SagaStep, broker_configured,
                         connect_broker, migrate, topology)

pytestmark = pytest.mark.integration

DATABASE_URL = os.environ.get("DATABASE_URL")
COMMAND = "process_autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework"
EVENT = "ProcessAutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkCompleted"

EXPORTER = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(EXPORTER))
trace.set_tracer_provider(_provider)


def uid() -> str:
    return uuid.uuid4().hex[:12]


@pytest.fixture(scope="module")
def broker():
    if not DATABASE_URL or not broker_configured():
        pytest.fail("Integration tests need DATABASE_URL and the broker variables (see docs/RUNTIME-KERNEL.md).")
    b = connect_broker()
    yield b
    b.close()


@pytest.fixture
def schema(broker):
    name = f"it_{uid()}"
    migrate(DATABASE_URL, name)
    EXPORTER.clear()
    yield name
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        conn.execute(f"DROP SCHEMA IF EXISTS {name} CASCADE")


def receive(broker, t, source: str, expected: int):
    """Receives and acknowledges messages until the expected number arrived and the source stays quiet for 0.5 s (10 s at most)."""
    out = []
    subscription = broker.subscribe(source, t)
    deadline = time.time() + 10
    quiet_since = time.time()
    try:
        while time.time() < deadline and (len(out) < expected or time.time() - quiet_since < 0.5):
            delivery = subscription.poll()
            if delivery is None:
                time.sleep(0.05)
                continue
            out.append(delivery.message)
            delivery.ack()
            quiet_since = time.time()
    finally:
        subscription.close()
    return out


@pytest.fixture
def t(broker, schema):
    # Brokers with fixed entities (Service Bus emulator) share one topology, emptied before each test.
    topo = topology(f"it-{uid()}") if broker.dynamic_topology else topology("it")
    broker.declare(topo)
    if not broker.dynamic_topology:
        receive(broker, topo, topo.queue, 0)
        receive(broker, topo, topo.dlq, 0)
    return topo


def count(schema: str, table: str, where: str = "true", params=()) -> int:
    with psycopg.connect(DATABASE_URL) as conn:
        return conn.execute(f"SELECT count(*) FROM {schema}.{table} WHERE {where}", params).fetchone()[0]


def test_it1_atomic_write_and_rollback(schema):
    service = CommandService(DATABASE_URL, schema)
    result = service.handle("t1", "agg-1", COMMAND)
    assert (result.status, result.event_type, result.version) == ("created", EVENT, 1)
    assert service.load("t1", "agg-1")["version"] == 1
    assert count(schema, "ghk_outbox", "aggregate_id = %s", ("agg-1",)) == 1
    with pytest.raises(DomainValidationError, match="Unknown command"):
        service.handle("t1", "agg-2", "no_such_command", idempotency_key="k-fail")
    assert service.load("t1", "agg-2") is None
    assert count(schema, "ghk_outbox", "aggregate_id = %s", ("agg-2",)) == 0
    assert count(schema, "ghk_idempotency", "key = %s", ("k-fail",)) == 0


def test_it2_concurrent_idempotent_requests(schema):
    service = CommandService(DATABASE_URL, schema)
    results = []
    threads = [threading.Thread(target=lambda: results.append(service.handle("t1", "agg-1", COMMAND, idempotency_key="key-1"))) for _ in range(5)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert count(schema, "ghk_outbox") == 1
    assert service.load("t1", "agg-1")["version"] == 1
    assert [r.status for r in results].count("created") == 1
    assert all((r.event_type, r.version) == (EVENT, 1) for r in results)


def test_it3_concurrent_relays_publish_exactly_once(broker, schema, t):
    service = CommandService(DATABASE_URL, schema)
    for i in range(20):
        service.handle("t1", f"agg-{i}", COMMAND)
    totals = {}

    def drain(worker: str):
        publisher = broker.publisher(t.exchange)
        relay = OutboxRelay(DATABASE_URL, publisher, schema)
        total = 0
        while True:
            n = relay.publish_batch(worker, 3)
            if n == 0:
                break
            total += n
        totals[worker] = total
        publisher.close()

    workers = [threading.Thread(target=drain, args=(w,)) for w in ("relay-a", "relay-b")]
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    assert sum(totals.values()) == 20
    assert count(schema, "ghk_outbox", "published_at IS NULL") == 0
    received = receive(broker, t, t.queue, 20)
    assert len(received) == 20
    assert len({m.message_id for m in received}) == 20


def test_it4_tenant_isolation(schema):
    service = CommandService(DATABASE_URL, schema)
    service.handle("tenant-a", "shared-id", COMMAND)
    assert service.load("tenant-b", "shared-id") is None
    service.handle("tenant-b", "shared-id", COMMAND)
    assert service.load("tenant-a", "shared-id")["version"] == 1
    assert service.load("tenant-b", "shared-id")["version"] == 1
    assert count(schema, "ghk_outbox", "tenant_id = %s", ("tenant-a",)) == 1


def test_it5_saga_compensates_in_reverse_order(schema):
    saga = SagaOrchestrator(DATABASE_URL, schema)
    log = []

    def step(name, fail=False):
        def action():
            if fail:
                raise RuntimeError(f"{name} failed")
            log.append(f"do:{name}")
        return SagaStep(name, action, lambda: log.append(f"undo:{name}"))

    assert saga.run("saga-1", "t1", [step("reserve"), step("charge"), step("ship", fail=True)]) == "COMPENSATED"
    assert log == ["do:reserve", "do:charge", "undo:charge", "undo:reserve"]
    assert saga.status("saga-1") == {"status": "COMPENSATED", "completed_steps": []}
    assert saga.run("saga-2", "t1", [step("reserve"), step("charge")]) == "COMPLETED"


def test_it6_inbox_deduplicates_and_dead_letters(broker, schema, t):
    handled = []

    def handler(event, meta):
        if event.get("poison"):
            raise RuntimeError("cannot process")
        handled.append(meta["message_id"])

    publisher = broker.publisher(t.exchange)
    for message_id, body in (("m-1", '{"ok": true}'), ("m-1", '{"ok": true}'), ("m-poison", '{"poison": true}')):
        publisher.publish(BrokerMessage(message_id, "Test", "t1", None, body.encode()))
    publisher.close()
    subscription = broker.subscribe(t.queue, t)
    InboxConsumer(DATABASE_URL, subscription, "it-consumer", handler, schema).drain()
    subscription.close()
    assert handled == ["m-1"]
    assert count(schema, "ghk_inbox", "consumer = %s", ("it-consumer",)) == 1
    assert [m.message_id for m in receive(broker, t, t.dlq, 1)] == ["m-poison"]


def test_it7_trace_context_propagation(broker, schema, t):
    service = CommandService(DATABASE_URL, schema)
    service.handle("t1", "agg-1", COMMAND, traceparent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01")
    with psycopg.connect(DATABASE_URL) as db:
        assert "4bf92f3577b34da6a3ce929d0e0e4736" in db.execute(f"SELECT traceparent FROM {schema}.ghk_outbox").fetchone()[0]
    publisher = broker.publisher(t.exchange)
    assert OutboxRelay(DATABASE_URL, publisher, schema).publish_batch("relay", 10) == 1
    publisher.close()
    received = []
    subscription = broker.subscribe(t.queue, t)
    InboxConsumer(DATABASE_URL, subscription, "trace-consumer", lambda event, meta: received.append(meta), schema).drain()
    subscription.close()
    assert len(received) == 1

    spans = EXPORTER.get_finished_spans()
    by_kind = {s.kind: s for s in spans}
    trace_id = format(by_kind[SpanKind.INTERNAL].context.trace_id, "032x")
    assert trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert format(by_kind[SpanKind.INTERNAL].parent.span_id, "016x") == "00f067aa0ba902b7"
    assert format(by_kind[SpanKind.PRODUCER].context.trace_id, "032x") == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert format(by_kind[SpanKind.CONSUMER].context.trace_id, "032x") == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert by_kind[SpanKind.CONSUMER].parent.span_id == by_kind[SpanKind.PRODUCER].context.span_id
