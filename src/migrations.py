"""Versioned SQLite migrations.

The database stores the number of the last migration it has run in
``PRAGMA user_version``. At startup, only migrations above that number run.
All pending migrations run in one transaction: if any step or the final
integrity checks fail, everything is rolled back and the version is unchanged.
Before migrating an existing database, a verified copy is written to the
backup path, replacing the previous copy.
"""

import os
import sqlite3
from collections.abc import Callable, Sequence
from contextlib import closing
from pathlib import Path

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


def backup_database(db: sqlite3.Connection, target: Path) -> None:
    """Write a verified copy of ``db`` to ``target``, replacing it only on success."""
    temporary = target.with_name(target.name + ".tmp")
    temporary.unlink(missing_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Backups contain password hashes: create the file private to the app user.
    os.close(os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
    try:
        with closing(sqlite3.connect(temporary)) as copy:
            db.backup(copy)
            # Only check integrity: a legacy source may have foreign-key
            # problems that the migration itself repairs.
            integrity = copy.execute("PRAGMA integrity_check").fetchall()
            if integrity != [("ok",)]:
                raise MigrationError(f"Backup integrity check failed: {integrity}")
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _has_tables(db: sqlite3.Connection) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone() is not None


def run_migrations(
    db: sqlite3.Connection,
    migrations: Sequence[Migration],
    backup_path: Path | None = None,
) -> int:
    """Run pending migrations and return the resulting schema version.

    ``migrations[0]`` is version 1, ``migrations[1]`` is version 2, and so on.
    With ``backup_path``, an existing database is backed up first; if the
    backup fails, nothing is migrated.
    """
    latest = len(migrations)
    current = schema_version(db)
    if current > latest:
        raise MigrationError(
            f"Database version {current} is newer than this app ({latest}); "
            "deploy the newer app or restore a matching backup"
        )

    if current < latest:
        if backup_path is not None and _has_tables(db):
            try:
                backup_database(db, backup_path)
            except Exception as error:
                raise MigrationError(
                    f"Pre-migration backup to {backup_path} failed; not migrating"
                ) from error
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
        print(f"Database migrated from version {current} to {latest}", flush=True)

    db.execute("PRAGMA foreign_keys = ON")
    if db.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise MigrationError("Could not enable foreign-key enforcement")
    return latest
