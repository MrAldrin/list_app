"""Limits on user text and on how many things may exist.

Text lengths are checked before writing. The database guards the text limits
(migration 6) as a safety net; checking here first gives the user a clear
message instead of a server error. Count limits are checked in
database_crud before a new row is inserted.
"""

MAX_NAME_LENGTH = 100  # Room, list and item names.
MAX_DESCRIPTION_LENGTH = 1000
MAX_TAG_LENGTH = 30
MIN_PASSWORD_LENGTH = 4  # Room passwords set from now on, in characters.
MAX_PASSWORD_LENGTH = 1024  # Passwords, in characters.

MAX_ITEMS_PER_LIST = 1000  # Checked and unchecked items together.
MAX_LISTS_PER_ROOM = 100
MAX_TAGS_PER_LIST = 50
# Sign-in sessions kept per room. A new sign-in drops the oldest ones.
MAX_SESSIONS_PER_ROOM = 200


def too_long_message(what: str, text: str, limit: int) -> str | None:
    """The message for the user when `text` is over `limit`; otherwise None."""
    if len(text) <= limit:
        return None
    return f"{what} can be at most {limit} characters"


def count_limit_message(subject: str, limit: int, noun: str) -> str:
    """The message for the user when a count limit is reached.

    For example: count_limit_message("A list", 1000, "items") gives
    "A list can have at most 1000 items".
    """
    return f"{subject} can have at most {limit} {noun}"
