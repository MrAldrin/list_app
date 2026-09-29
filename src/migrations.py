"""Versioned SQLite migrations.

The database stores the number of the last migration it has run in
``PRAGMA user_version``. At startup, only migrations above that number run.
All pending migrations run in one transaction: if any step or the final
integrity checks fail, everything is rolled back and the version is unchanged.
"""

import sqlite3
from collections.abc import Callable, Sequence

Migration = Callable[[sqlite3.Connection], None]


class MigrationError(RuntimeError):
    """Raised when migrations cannot run or leave invalid data."""


def schema_version(db: sqlite3.Connection) -> int:
    return db.execute("PRAGMA user_version").fetchone()[0]


def _check_integrity(db: sqlite3.Connection) -> None:
    integrity = db.execute("PRAGMA integrity_check").fetchall()
    if integrity != [("ok",)]:
        raise MigrationError(f"Integrity check failed after migration: {integrity}")
    foreign_key_errors = db.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_errors:
        raise MigrationError(
            f"Foreign-key check failed after migration: {foreign_key_errors}"
        )


def run_migrations(db: sqlite3.Connection, migrations: Sequence[Migration]) -> int:
    """Run pending migrations and return the resulting schema version.

    ``migrations[0]`` is version 1, ``migrations[1]`` is version 2, and so on.
    """
    latest = len(migrations)
    current = schema_version(db)
    if current > latest:
        raise MigrationError(
            f"Database version {current} is newer than this app ({latest}); "
            "deploy the newer app or restore a matching backup"
        )

    if current < latest:
        # Table rebuilds need foreign keys off, and SQLite ignores this pragma
        # inside a transaction, so switch it before BEGIN.
        db.execute("PRAGMA foreign_keys = OFF")
        # Python's sqlite3 does not open a transaction before CREATE/ALTER, so
        # start one explicitly to make schema changes roll back too.
        db.execute("BEGIN IMMEDIATE")
        try:
            for migration in migrations[current:]:
                migration(db)
            _check_integrity(db)
            db.execute(f"PRAGMA user_version = {latest}")
            db.commit()
        except BaseException:
            db.rollback()
            raise

    db.execute("PRAGMA foreign_keys = ON")
    if db.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise MigrationError("Could not enable foreign-key enforcement")
    return latest
