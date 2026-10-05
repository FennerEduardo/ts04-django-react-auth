"""W3C trace-context helpers. Spans go to the globally configured tracer provider
(configure exporters with the standard OTEL_* environment variables)."""
from __future__ import annotations

from typing import Optional

from opentelemetry import context as otel_context, trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

_propagator = TraceContextTextMapPropagator()


def tracer() -> trace.Tracer:
    return trace.get_tracer("autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework")


def context_from(traceparent: Optional[str]) -> otel_context.Context:
    """Context whose parent is the span described by an incoming traceparent header."""
    if not traceparent:
        return otel_context.get_current()
    return _propagator.extract({"traceparent": traceparent})


def traceparent_of(ctx: otel_context.Context) -> Optional[str]:
    carrier: dict = {}
    _propagator.inject(carrier, context=ctx)
    return carrier.get("traceparent")
