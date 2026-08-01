"""Assigns X-Request-ID, updates the logging context, and records metrics."""

import re
import time
import uuid
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings
from app.core.middleware.context import request_id_var
from app.core.middleware.metrics import record_request


def _decode(value: bytes | None) -> str | None:
    return value.decode("latin-1") if value else None


_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def normalize_path(path: str) -> str:
    """Collapse UUIDs/trailing ids so metric labels stay bounded."""
    path = _UUID_RE.sub("{id}", path)
    return path


class RequestContextMiddleware:
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

        span: Any = None
        if settings.ENABLE_OTEL:
            from app.core.telemetry import get_tracer

            tracer = get_tracer()
            if tracer is not None:
                span = tracer.start_span(
                    f"{scope.get('method', '')} {scope.get('path', '')}"
                )
                span.set_attribute("http.request_id", request_id)

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
            if span is not None:
                span.set_attribute("http.status_code", status_holder["status"])
                span.end()
            record_request(
                scope.get("method", ""),
                normalize_path(scope.get("path", "")),
                status_holder["status"],
                time.perf_counter() - start,
            )
