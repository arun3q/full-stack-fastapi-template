"""Pure-ASGI middleware: request ID, structured-logging context, metrics and idempotency."""

import contextvars
import logging
import time
import uuid
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.cache import cache_get, cache_set
from app.core.config import settings

logger = logging.getLogger(__name__)

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)

_IDEMPOTENCY_TTL = 3600  # 1 hour
_IDEMPOTENCY_METHODS = {"POST", "PUT", "PATCH"}

# Prometheus metrics (lazy import so the endpoint works even if disabled here)
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


class RequestContextMiddleware:
    """Assigns X-Request-ID, updates the logging context, and records metrics."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        request_id = _decode(headers.get(b"x-request-id")) or uuid.uuid4().hex[:16]
        scope["state"]["request_id"] = request_id
        token = request_id_var.set(request_id)

        start = time.perf_counter()
        status_holder: dict[str, int] = {"status": 0}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                outgoing = list(message.get("headers") or [])
                outgoing.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = outgoing
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            request_id_var.reset(token)
            duration = time.perf_counter() - start
            if _metrics_enabled and _requests_counter is not None:
                path = scope.get("path", "")
                method = scope.get("method", "")
                _requests_counter.labels(
                    method, path, str(status_holder["status"])
                ).inc()
                _request_duration.labels(method, path).observe(duration)


class IdempotencyMiddleware:
    """Replays POST/PUT/PATCH requests that carry an ``Idempotency-Key`` header.

    Only buffers the response for idempotent requests (JSON), so streaming
    endpoints are unaffected.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        method = scope.get("method", "")
        key = _decode(headers.get(b"idempotency-key"))
        if not key or method not in _IDEMPOTENCY_METHODS:
            await self.app(scope, receive, send)
            return

        cache_key = f"idem:{key}"
        cached = await cache_get(cache_key)
        if cached is not None and isinstance(cached, dict):
            await _send_cached(cached, send)
            return

        # Buffer the response so we can replay it on a repeat request
        state: dict[str, Any] = {"code": 200, "headers": [], "body": b""}

        async def buffer_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                state["code"] = message["status"]
                state["headers"] = list(message.get("headers") or [])
            elif message["type"] == "http.response.body":
                state["body"] = state["body"] + message.get("body", b"")

        await self.app(scope, receive, buffer_send)

        body = state["body"]
        response_headers = state["headers"]
        content_type = _decode(dict(response_headers).get(b"content-type")) or ""
        if "text/event-stream" in content_type:
            # Don't cache streaming responses
            await _send_raw(state["code"], response_headers, body, send)
            return

        await cache_set(
            cache_key,
            {
                "status": state["code"],
                "headers": [
                    [k.decode("latin-1"), v.decode("latin-1")]
                    for k, v in response_headers
                ],
                "body": body.decode("utf-8", errors="replace"),
            },
            ttl_seconds=_IDEMPOTENCY_TTL,
        )
        await _send_raw(state["code"], response_headers, body, send)


async def _send_cached(payload: dict[str, Any], send: Send) -> None:
    status = int(payload.get("status", 200))
    headers = [
        (k.encode("latin-1"), v.encode("latin-1"))
        for k, v in payload.get("headers", [])
    ]
    body = str(payload.get("body", "")).encode("utf-8")
    await _send_raw(status, headers, body, send)


async def _send_raw(
    status: int, headers: list[tuple[bytes, bytes]], body: bytes, send: Send
) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": headers,
        }
    )
    await send({"type": "http.response.body", "body": body})


def _decode(value: bytes | None) -> str | None:
    return value.decode("latin-1") if value else None
