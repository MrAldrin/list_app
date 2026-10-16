"""The one place that hashes room passwords.

Kept apart from database_crud: database_setup needs it, and
database_crud imports database_setup, so importing it from there would cycle.
"""

import bcrypt


def hash_password(plain: str) -> str:
    """A bcrypt hash of a room password, as text."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
