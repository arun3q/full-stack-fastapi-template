"""Prometheus metrics helpers (idempotently registered)."""

from typing import Any

from app.core.config import settings

_metrics_enabled = False
_metrics_initialized = False
_requests_counter: Any = None
_request_duration: Any = None


def init_metrics() -> None:
    global _metrics_enabled, _metrics_initialized, _requests_counter, _request_duration
    if _metrics_initialized or not settings.ENABLE_METRICS:
        return
    from prometheus_client import Counter, Histogram

    _requests_counter = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
    )
    _request_duration = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency (seconds)",
        ["method", "path"],
    )
    _metrics_enabled = True
    _metrics_initialized = True


def record_request(method: str, path: str, status: int, duration: float) -> None:
    if _metrics_enabled and _requests_counter is not None:
        _requests_counter.labels(method, path, str(status)).inc()
        _request_duration.labels(method, path).observe(duration)
