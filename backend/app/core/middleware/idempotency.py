"""Replays POST/PUT/PATCH requests that carry an ``Idempotency-Key`` header.

Only buffers the response for idempotent requests (JSON), so streaming
endpoints are unaffected.
"""

from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.cache import cache_get, cache_set

_IDEMPOTENCY_TTL = 3600  # 1 hour
_IDEMPOTENCY_METHODS = {"POST", "PUT", "PATCH"}


def _decode(value: bytes | None) -> str | None:
    return value.decode("latin-1") if value else None


class IdempotencyMiddleware:
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

        # Scope the idempotency key to the method + path + caller identity so
        # different users/tenants can never collide or replay each other's bodies.
        identity = _decode(headers.get(b"x-organization-id")) or "anon"
        authorization = _decode(headers.get(b"authorization")) or ""
        if authorization.startswith("Bearer "):
            identity += ":" + authorization[7:24]  # short token fingerprint
        cache_key = f"idem:{method}:{scope.get('path', '')}:{identity}:{key}"
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

        if state["code"] < 400:
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
