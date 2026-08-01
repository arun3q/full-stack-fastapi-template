"""Request body size limit (reject oversized payloads with 413)."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int = _MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        length = headers.get(b"content-length")
        if length:
            try:
                if int(length) > self.max_bytes:
                    await _reject(send)
                    return
            except ValueError:
                pass

        # Count body bytes as they stream through
        body_bytes = 0

        async def wrapped_receive() -> Message:
            nonlocal body_bytes
            message = await receive()
            if message["type"] == "http.request":
                body_bytes += len(message.get("body", b""))
                if body_bytes > self.max_bytes:
                    raise _BodyTooLarge()
            return message

        try:
            await self.app(scope, wrapped_receive, send)
        except _BodyTooLarge:
            await _reject(send)


class _BodyTooLarge(Exception):
    pass


async def _reject(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send(
        {"type": "http.response.body", "body": b'{"detail":"Request body too large"}'}
    )
