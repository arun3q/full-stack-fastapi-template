"""OpenTelemetry tracing (optional toggle).

When ``ENABLE_OTEL`` is true, a tracer provider is configured and every request
gets a span. Replace the console exporter with an OTLP exporter in production.
"""

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_initialized = False


def init_telemetry() -> None:
    global _initialized
    if _initialized or not settings.ENABLE_OTEL:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            ConsoleSpanExporter,
            SimpleSpanProcessor,
        )

        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)
        _initialized = True
        logger.info("OpenTelemetry tracing enabled")
    except Exception:
        logger.warning("Failed to initialize OpenTelemetry", exc_info=True)


def get_tracer() -> Any:
    if not settings.ENABLE_OTEL:
        return None
    from opentelemetry import trace

    return trace.get_tracer("full-stack-fastapi-template")
