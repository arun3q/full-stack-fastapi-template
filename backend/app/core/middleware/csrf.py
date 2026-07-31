"""CSRF protection for cookie-based auth (``AUTH_TOKEN_IN_COOKIE``).

Double-submit pattern: login sets a ``csrf_token`` cookie; state-changing
requests authenticated via the session cookie must echo it in the
``X-CSRF-Token`` header. Bearer/API-key requests are unaffected.
"""

import hmac

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _decode(value: bytes | None) -> str | None:
    return value.decode("latin-1") if value else None


class CSRFMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not settings.AUTH_TOKEN_IN_COOKIE:
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        if method not in _UNSAFE_METHODS:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        # Only enforce for cookie-authenticated requests (no bearer token)
        if b"authorization" in headers or b"x-api-key" in headers:
            await self.app(scope, receive, send)
            return
        if b"access_token" not in headers.get(b"cookie", b""):
            await self.app(scope, receive, send)
            return

        cookie_token = _decode(headers.get(b"cookie")) or ""
        csrf_cookie = ""
        for part in cookie_token.split("; "):
            if part.startswith("csrf_token="):
                csrf_cookie = part[len("csrf_token=") :]
                break
        header_token = _decode(headers.get(b"x-csrf-token")) or ""
        if not csrf_cookie or not hmac.compare_digest(csrf_cookie, header_token):
            await _reject(send)
            return

        await self.app(scope, receive, send)


async def _reject(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 403,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send(
        {"type": "http.response.body", "body": b'{"detail":"CSRF validation failed"}'}
    )
