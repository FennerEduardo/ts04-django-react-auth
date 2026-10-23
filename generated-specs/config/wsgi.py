import os

from django.core.wsgi import get_wsgi_application

from app.runtime.otel import start_telemetry

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
# OTLP export when OTEL_EXPORTER_OTLP_ENDPOINT is set (one tracer provider per gunicorn worker).
start_telemetry()
application = get_wsgi_application()
