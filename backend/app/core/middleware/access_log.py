"""JSON access-log middleware: one structured line per request."""

import logging
import time
from urllib.parse import unquote

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.middleware.context import request_id_var

logger = logging.getLogger("access")


class AccessLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        start = time.perf_counter()
        status_code = 0

        async def _send(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, _send)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            path = unquote(scope.get("path", ""))
            logger.info(
                "request",
                extra={
                    "method": scope.get("method", ""),
                    "path": path,
                    "status": status_code,
                    "duration_ms": round(duration_ms, 2),
                    "request_id": request_id_var.get(),
                },
            )
