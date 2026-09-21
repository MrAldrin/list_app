"""HTTPS-only remembered access; cookies carry existing revocable room tokens."""

import hashlib
import sqlite3

from fastapi import Request
from fastapi.responses import Response

from database_crud import validate_room_access_token

MAX_AGE = 60 * 60 * 24 * 365
LAST_ROOM_COOKIE = "__Host-listapp-last-room"


def token_cookie_name(slug: str) -> str:
    return "__Host-listapp-room-" + hashlib.sha256(slug.encode()).hexdigest()


def same_origin_socket(origin: str, environ: dict) -> bool:
    """Use ASGI's proxy-normalized scheme, not Engine.IO's HTTP default."""
    scope = environ.get("asgi.scope", {})
    scheme = {"wss": "https", "ws": "http"}.get(
        scope.get("scheme"), scope.get("scheme")
    )
    host = environ.get("HTTP_HOST")
    return bool(scheme in {"http", "https"} and host and origin == f"{scheme}://{host}")


def register_room_cookie_routes(app) -> None:
    @app.post("/_room-access/{slug}")
    async def remember(slug: str, request: Request) -> Response:
        # A custom header prevents HTML forms; exact Origin checking also rejects
        # cross-origin fetches. Never enable CORS on this endpoint.
        headers = {"Cache-Control": "no-store"}
        if (
            request.url.scheme != "https"
            or request.headers.get("origin") != str(request.base_url).rstrip("/")
            or request.headers.get("x-listapp-request") != "1"
            or request.headers.get("sec-fetch-site") not in (None, "same-origin")
        ):
            return Response(status_code=403, headers=headers)
        try:
            data = await request.json()
        except ValueError:
            return Response(status_code=400, headers=headers)
        if not isinstance(data, dict):
            return Response(status_code=400, headers=headers)
        name = token_cookie_name(slug)
        response = Response(status_code=204, headers=headers)
        if data.get("clear") is True:
            response.delete_cookie(name, secure=True, httponly=True, samesite="lax")
            return response
        token = data.get("token")
        if not isinstance(token, str) or len(token) > 256:
            return Response(status_code=400, headers=headers)
        try:
            valid = validate_room_access_token(slug, token)
        except sqlite3.Error:
            return Response(status_code=503, headers=headers)
        if valid is None:
            return Response(status_code=401, headers=headers)
        if data.get("check") is True:
            return Response(
                status_code=204 if request.cookies.get(name) == token else 401,
                headers=headers,
            )
        for key, value in ((name, token), (LAST_ROOM_COOKIE, slug)):
            response.set_cookie(
                key,
                value,
                max_age=MAX_AGE,
                secure=True,
                httponly=True,
                samesite="lax",
                path="/",
            )
        return response
