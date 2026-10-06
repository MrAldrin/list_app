"""Admin sign-in rules for the JSON API.

The admin password is `APP_PASSWORD`. The API has its own admin session
cookie (decision 144): a signed token that carries an expiry and
is signed with a key made from the current `APP_PASSWORD`. Changing the
password therefore ends every admin session, and no admin state is stored on
the server. Admin sign-in never grants room access.
"""

import hashlib
import hmac
import secrets
import time

from config import require_app_password

# How long an admin session lasts (as NiceGUI's session cookie: 14 days).
ADMIN_SESSION_SECONDS = 60 * 60 * 24 * 14
MAX_ADMIN_TOKEN_LENGTH = 256
_TOKEN_VERSION = "v1"
_DOMAIN = b"listapp-admin-session\0"


def _sign(payload: str) -> str:
    key = require_app_password().encode("utf-8", "surrogatepass")
    message = _DOMAIN + payload.encode("ascii")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def issue_admin_token(now: float | None = None) -> str:
    """A fresh signed token: `v1.<expiry>.<nonce>.<signature>`."""
    expires = int((time.time() if now is None else now) + ADMIN_SESSION_SECONDS)
    payload = f"{_TOKEN_VERSION}.{expires}.{secrets.token_hex(16)}"
    return f"{payload}.{_sign(payload)}"


def admin_token_valid(token: str | None, now: float | None = None) -> bool:
    """True for an unexpired token signed with the current APP_PASSWORD."""
    if not token or len(token) > MAX_ADMIN_TOKEN_LENGTH or not token.isascii():
        return False
    parts = token.split(".")
    if len(parts) != 4 or parts[0] != _TOKEN_VERSION or not parts[1].isdigit():
        return False
    payload = ".".join(parts[:3])
    if not hmac.compare_digest(parts[3].encode(), _sign(payload).encode()):
        return False
    return int(parts[1]) > (time.time() if now is None else now)


def admin_password_matches(candidate: str) -> bool:
    """Compare with APP_PASSWORD in constant time (same result as `==`)."""
    expected = require_app_password()
    # `surrogatepass` keeps any Python string comparable, as `==` would.
    return hmac.compare_digest(
        candidate.encode("utf-8", "surrogatepass"),
        expected.encode("utf-8", "surrogatepass"),
    )
