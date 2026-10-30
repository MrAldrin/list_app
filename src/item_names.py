"""Item-name normalization shared by Python writes and SQLite's safety guard."""

import sqlite3


def normalize_item_name(raw: str | None) -> str:
    """Trim an item name without changing the case people entered."""
    return (raw or "").strip()


def item_name_key(name: str) -> str:
    """The Unicode-aware, case-insensitive key used to find duplicate items."""
    return name.strip().lower()


def _sqlite_item_name_key(raw: object) -> str:
    """Return a safe key from a SQLite value, including malformed values."""
    if not isinstance(raw, str):
        return ""
    return item_name_key(raw)


def register_sqlite_item_name_key(db: sqlite3.Connection) -> None:
    """Register the Python-lower function used by item-name guard triggers."""
    db.create_function(
        "listr_item_name_key", 1, _sqlite_item_name_key, deterministic=True
    )
