"""Shared helpers for slugs, UUID strings and stored token hashes."""

import hashlib
import re
import uuid


def make_slug(name: str) -> str:
    """A URL slug: the name in a-z0-9 and dashes, plus 6 random hex digits."""
    safe_name = re.sub(r"[^a-z0-9]", "-", name.lower().strip())
    short_uuid = str(uuid.uuid4())[:6]
    return f"{safe_name}-{short_uuid}"


def canonical_uuid(value: str) -> str:
    """The lowercase, hyphenated form of a UUID string. Raises ValueError if invalid."""
    return str(uuid.UUID(value))


def token_hash(token: str) -> str:
    """The sha256 hex digest stored in the database instead of a token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
