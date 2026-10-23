import importlib

import pytest

GENERATED_MODULES = [
    "app",
    "app.apps",
    "app.auth",
    "app.domain",
    "app.domain.autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework",
    "app.domain.errors",
    "app.infrastructure",
    "app.infrastructure.event_bus",
    "app.management",
    "app.management.commands",
    "app.management.commands.outbox_relay",
    "app.runtime",
    "app.runtime.broker",
    "app.runtime.command_service",
    "app.runtime.inbox_consumer",
    "app.runtime.otel",
    "app.runtime.outbox_relay",
    "app.runtime.saga",
    "app.runtime.schema",
    "app.runtime.telemetry",
    "app.views",
    "app.worker",
    "config",
    "config.settings",
    "config.urls",
]


@pytest.mark.parametrize("module", GENERATED_MODULES)
def test_generated_module_imports(module):
    importlib.import_module(module)
