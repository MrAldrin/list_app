"""Shared setup for the migration tests: the app's real migrations (database_setup)."""

import sqlite3

from database_setup import _migrations
from migrations import run_migrations

LATEST_VERSION = len(_migrations("unused"))


def migrate_to(db: sqlite3.Connection, version: int = LATEST_VERSION) -> None:
    """Run the app's migrations up to `version` (1 is the first migration)."""
    run_migrations(db, _migrations("pw")[:version])
