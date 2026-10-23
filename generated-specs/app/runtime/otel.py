"""OpenTelemetry export of the running service.

With OTEL_EXPORTER_OTLP_ENDPOINT set, spans go over OTLP/HTTP to that collector (service.name from
OTEL_SERVICE_NAME); without it nothing is exported and nothing connects."""
from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_provider: TracerProvider | None = None


def start_telemetry(service_name: str = "django-react-auth") -> bool:
    global _provider
    if _provider is not None or not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return False
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    _provider = TracerProvider(resource=Resource.create({"service.name": os.environ.get("OTEL_SERVICE_NAME") or service_name}))
    _provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(_provider)
    return True


def stop_telemetry() -> None:
    """Flushes the pending spans (call on shutdown)."""
    if _provider is not None:
        _provider.shutdown()
