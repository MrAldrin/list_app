"""Security headers on every response: no framing and no MIME sniffing.

A pure ASGI middleware, so streamed responses (live update streams) pass
straight through. The headers replace any copy a route already set.

There is no full Content-Security-Policy here: the app shell has an inline
theme script, and a full policy is a separate decision.
"""

from typing import Any

SECURITY_HEADERS: dict[bytes, bytes] = {
    b"x-content-type-options": b"nosniff",
    b"x-frame-options": b"DENY",
    b"content-security-policy": b"frame-ancestors 'none'",
}


class SecurityHeadersMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() not in SECURITY_HEADERS
                ]
                headers.extend(SECURITY_HEADERS.items())
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
