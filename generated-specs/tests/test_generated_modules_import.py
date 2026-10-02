import importlib

import pytest

GENERATED_MODULES = [
    "app",
    "app.apps",
    "app.domain",
    "app.domain.autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework",
    "app.infrastructure",
    "app.infrastructure.event_bus",
    "app.migrations",
    "app.migrations.0001_initial",
    "app.models",
    "app.outbox",
    "app.views",
    "config",
    "config.settings",
    "config.urls",
]


@pytest.mark.parametrize("module", GENERATED_MODULES)
def test_generated_module_imports(module):
    importlib.import_module(module)
