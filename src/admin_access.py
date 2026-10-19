"""Admin sign-in rules for the JSON API.

The admin password is `APP_PASSWORD`. The API has its own admin session
cookie (decision 144): a signed token that carries an expiry and is signed
with a key derived from the current `APP_PASSWORD`. Changing the password
therefore ends every admin session, and no admin state is stored on the
server. Admin sign-in never grants room access.

The key is derived with scrypt, a slow function, so a stolen cookie allows
only slow offline guessing. A fast hash (HMAC or HKDF over the password) would
allow millions of guesses a second.
"""

import functools
import hashlib
import hmac
import secrets
import time

from config import require_app_password

# How long an admin session lasts (14 days, as the earlier admin session).
ADMIN_SESSION_SECONDS = 60 * 60 * 24 * 14
MAX_ADMIN_TOKEN_LENGTH = 256
# v2 signs with the scrypt key. v1 tokens (signed with the raw password) are
# refused, so every admin signs in again once after this change.
_TOKEN_VERSION = "v2"
_DOMAIN = b"listapp-admin-session\0"
# Fixed label for the key derivation. Changing it signs out every admin.
_KEY_SALT = b"listr-admin-cookie-v2"
# scrypt cost: N=2**16, r=8, p=1. About 140 ms on the dev machine, 64 MB while
# it runs. The key is derived once per process for each password.
_SCRYPT_N = 2**16
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_MAXMEM = 128 * 1024 * 1024  # Must be more than 128 * r * n (64 MB).


@functools.lru_cache(maxsize=4)
def _signing_key(password: str) -> bytes:
    """The HMAC key for `password`. Slow on purpose; cached per password."""
    return hashlib.scrypt(
        password.encode("utf-8", "surrogatepass"),
        salt=_KEY_SALT,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=32,
        maxmem=_SCRYPT_MAXMEM,
    )


def _sign(payload: str) -> str:
    key = _signing_key(require_app_password())
    message = _DOMAIN + payload.encode("ascii")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def issue_admin_token(now: float | None = None) -> str:
    """A fresh signed token: `v2.<expiry>.<nonce>.<signature>`."""
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
