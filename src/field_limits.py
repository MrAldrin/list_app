"""Length limits for user text, checked before writing.

The database guards the same limits (migration 6) as a safety net; checking
here first gives the user a clear message instead of a server error.
"""

MAX_NAME_LENGTH = 100  # Room, list and item names.
MAX_DESCRIPTION_LENGTH = 1000
MAX_TAG_LENGTH = 30


def too_long_message(what: str, text: str, limit: int) -> str | None:
    """The message for the user when `text` is over `limit`; otherwise None."""
    if len(text) <= limit:
        return None
    return f"{what} can be at most {limit} characters"
