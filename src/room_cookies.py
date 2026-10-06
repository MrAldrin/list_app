"""Names and rules of the room cookies. The API sets them (src/api/access.py)."""

import hashlib

from fastapi import Request

MAX_AGE = 60 * 60 * 24 * 365
# Browsers accept __Host- cookies only with Secure, Path=/ and no Domain, so a
# subdomain or a plain-HTTP response can never set or overwrite them.
HOST_PREFIX = "__Host-"
PLAIN_LAST_ROOM_COOKIE = "listapp-last-room"
LAST_ROOM_COOKIE = HOST_PREFIX + PLAIN_LAST_ROOM_COOKIE


def plain_token_cookie_name(slug: str) -> str:
    """Cookie name without the __Host- prefix (plain-HTTP JSON API only)."""
    return "listapp-room-" + hashlib.sha256(slug.encode()).hexdigest()


def token_cookie_name(slug: str) -> str:
    return HOST_PREFIX + plain_token_cookie_name(slug)


def is_same_origin_request(request: Request) -> bool:
    """True only for a browser request sent by a page of this exact origin.

    Origin must equal this server's scheme and host (proxy-normalized by the
    ASGI server), and Sec-Fetch-Site, when the browser sends it, must agree.
    """
    origin_ok = request.headers.get("origin") == str(request.base_url).rstrip("/")
    return origin_ok and request.headers.get("sec-fetch-site") in (None, "same-origin")
