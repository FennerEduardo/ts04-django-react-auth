"""Runtime integration tests (docs/RUNTIME-KERNEL.md, IT1-IT7) against PostgreSQL and RabbitMQ.
Requires DATABASE_URL and AMQP_URL. Run with: pytest -m integration"""
import os
import threading
import time
import uuid

import pika
import psycopg
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind

from app.domain import DomainValidationError
from app.runtime import CommandService, InboxConsumer, OutboxRelay, SagaOrchestrator, SagaStep, declare_topology, migrate, topology

pytestmark = pytest.mark.integration

DATABASE_URL = os.environ.get("DATABASE_URL")
AMQP_URL = os.environ.get("AMQP_URL")
COMMAND = "process_autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework"
EVENT = "ProcessAutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkCompleted"

EXPORTER = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(EXPORTER))
trace.set_tracer_provider(_provider)


def uid() -> str:
    return uuid.uuid4().hex[:12]


@pytest.fixture
def schema():
    if not DATABASE_URL or not AMQP_URL:
        pytest.fail("Integration tests need DATABASE_URL and AMQP_URL (see docs/RUNTIME-KERNEL.md).")
    name = f"it_{uid()}"
    migrate(DATABASE_URL, name)
    EXPORTER.clear()
    yield name
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        conn.execute(f"DROP SCHEMA IF EXISTS {name} CASCADE")


@pytest.fixture
def t():
    return topology(f"it-{uid()}")


def channel():
    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
    return connection, connection.channel()


def count(schema: str, table: str, where: str = "true", params=()) -> int:
    with psycopg.connect(DATABASE_URL) as conn:
        return conn.execute(f"SELECT count(*) FROM {schema}.{table} WHERE {where}", params).fetchone()[0]


def drain_queue(ch, queue: str):
    messages = []
    while True:
        method, properties, body = ch.basic_get(queue, auto_ack=True)
        if method is None:
            return messages
        messages.append(properties)


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


def test_it3_concurrent_relays_publish_exactly_once(schema, t):
    service = CommandService(DATABASE_URL, schema)
    for i in range(20):
        service.handle("t1", f"agg-{i}", COMMAND)
    setup_conn, setup = channel()
    declare_topology(setup, t)
    totals = {}

    def drain(worker: str):
        conn, ch = channel()
        relay = OutboxRelay(DATABASE_URL, ch, t.exchange, schema)
        total = 0
        while True:
            n = relay.publish_batch(worker, 3)
            if n == 0:
                break
            total += n
        totals[worker] = total
        conn.close()

    workers = [threading.Thread(target=drain, args=(w,)) for w in ("relay-a", "relay-b")]
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    assert sum(totals.values()) == 20
    assert count(schema, "ghk_outbox", "published_at IS NULL") == 0
    deadline = time.time() + 10
    while setup.queue_declare(queue=t.queue, passive=True).method.message_count < 20 and time.time() < deadline:
        time.sleep(0.05)
    ids = [p.message_id for p in drain_queue(setup, t.queue)]
    assert len(set(ids)) == 20
    setup_conn.close()


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


def test_it6_inbox_deduplicates_and_dead_letters(schema, t):
    conn, ch = channel()
    declare_topology(ch, t)
    handled = []

    def handler(event, meta):
        if event.get("poison"):
            raise RuntimeError("cannot process")
        handled.append(meta["message_id"])

    def publish(message_id, body):
        ch.basic_publish(t.exchange, "Test", body.encode(), pika.BasicProperties(message_id=message_id, headers={"tenant_id": "t1"}))

    publish("m-1", '{"ok": true}')
    publish("m-1", '{"ok": true}')
    publish("m-poison", '{"poison": true}')
    InboxConsumer(DATABASE_URL, ch, t.queue, "it-consumer", handler, schema).drain()
    assert handled == ["m-1"]
    assert count(schema, "ghk_inbox", "consumer = %s", ("it-consumer",)) == 1
    deadline = time.time() + 10
    while ch.queue_declare(queue=t.dlq, passive=True).method.message_count < 1 and time.time() < deadline:
        time.sleep(0.05)
    assert [p.message_id for p in drain_queue(ch, t.dlq)] == ["m-poison"]
    conn.close()


def test_it7_trace_context_propagation(schema, t):
    service = CommandService(DATABASE_URL, schema)
    service.handle("t1", "agg-1", COMMAND, traceparent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01")
    with psycopg.connect(DATABASE_URL) as db:
        assert "4bf92f3577b34da6a3ce929d0e0e4736" in db.execute(f"SELECT traceparent FROM {schema}.ghk_outbox").fetchone()[0]
    conn, ch = channel()
    declare_topology(ch, t)
    assert OutboxRelay(DATABASE_URL, ch, t.exchange, schema).publish_batch("relay", 10) == 1
    received = []
    InboxConsumer(DATABASE_URL, ch, t.queue, "trace-consumer", lambda event, meta: received.append(meta), schema).drain()
    conn.close()
    assert len(received) == 1

    spans = EXPORTER.get_finished_spans()
    by_kind = {s.kind: s for s in spans}
    trace_id = format(by_kind[SpanKind.INTERNAL].context.trace_id, "032x")
    assert trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert format(by_kind[SpanKind.INTERNAL].parent.span_id, "016x") == "00f067aa0ba902b7"
    assert format(by_kind[SpanKind.PRODUCER].context.trace_id, "032x") == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert format(by_kind[SpanKind.CONSUMER].context.trace_id, "032x") == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert by_kind[SpanKind.CONSUMER].parent.span_id == by_kind[SpanKind.PRODUCER].context.span_id
