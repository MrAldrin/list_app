import sqlite3

import pytest

from migrations import MigrationError, run_migrations, schema_version


def _connect(tmp_path) -> sqlite3.Connection:
    return sqlite3.connect(tmp_path / "migrations.db")


def _table_names(db: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }


def _create_parents(db: sqlite3.Connection) -> None:
    db.execute("CREATE TABLE parents (id INTEGER PRIMARY KEY)")


def _create_children(db: sqlite3.Connection) -> None:
    db.execute(
        "CREATE TABLE children (id INTEGER PRIMARY KEY, "
        "parent_id INTEGER NOT NULL REFERENCES parents(id))"
    )


def test_fresh_database_runs_all_migrations_in_order(tmp_path):
    db = _connect(tmp_path)

    assert run_migrations(db, [_create_parents, _create_children]) == 2

    assert schema_version(db) == 2
    assert {"parents", "children"} <= _table_names(db)
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_up_to_date_database_runs_nothing(tmp_path):
    db = _connect(tmp_path)
    run_migrations(db, [_create_parents])
    calls = []

    run_migrations(db, [lambda _db: calls.append("again")])

    assert calls == []
    assert schema_version(db) == 1


def test_only_pending_migrations_run(tmp_path):
    db = _connect(tmp_path)
    run_migrations(db, [_create_parents])

    run_migrations(db, [_create_parents, _create_children])

    assert schema_version(db) == 2
    assert "children" in _table_names(db)


def test_failure_rolls_back_schema_changes_and_keeps_version(tmp_path):
    db = _connect(tmp_path)
    run_migrations(db, [_create_parents])

    def create_then_fail(db: sqlite3.Connection) -> None:
        db.execute("ALTER TABLE parents ADD COLUMN name TEXT")
        db.execute("CREATE TABLE half_done (id INTEGER)")
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        run_migrations(db, [_create_parents, _create_children, create_then_fail])

    assert schema_version(db) == 1
    assert "children" not in _table_names(db)
    assert "half_done" not in _table_names(db)
    columns = {row[1] for row in db.execute("PRAGMA table_info(parents)")}
    assert "name" not in columns


def test_foreign_key_failure_rolls_back(tmp_path):
    db = _connect(tmp_path)
    run_migrations(db, [_create_parents, _create_children])

    def add_orphan(db: sqlite3.Connection) -> None:
        db.execute("INSERT INTO children (id, parent_id) VALUES (1, 999)")

    with pytest.raises(MigrationError, match="Foreign-key check failed"):
        run_migrations(db, [_create_parents, _create_children, add_orphan])

    assert schema_version(db) == 2
    assert db.execute("SELECT COUNT(*) FROM children").fetchone()[0] == 0


def test_table_rebuild_works_with_foreign_keys_off(tmp_path):
    db = _connect(tmp_path)
    run_migrations(db, [_create_parents, _create_children])
    db.execute("INSERT INTO parents (id) VALUES (1)")
    db.execute("INSERT INTO children (id, parent_id) VALUES (1, 1)")
    db.commit()

    def rebuild_parents(db: sqlite3.Connection) -> None:
        # SQLite's documented rebuild order. Renaming the old table first would
        # repoint the children's foreign key at it.
        db.execute("CREATE TABLE parents_new (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        db.execute("INSERT INTO parents_new (id) SELECT id FROM parents")
        db.execute("DROP TABLE parents")
        db.execute("ALTER TABLE parents_new RENAME TO parents")

    run_migrations(db, [_create_parents, _create_children, rebuild_parents])

    assert schema_version(db) == 3
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert db.execute("SELECT parent_id FROM children").fetchall() == [(1,)]


def test_newer_database_than_app_is_refused(tmp_path):
    db = _connect(tmp_path)
    run_migrations(db, [_create_parents, _create_children])

    with pytest.raises(MigrationError, match="newer than this app"):
        run_migrations(db, [_create_parents])

    assert schema_version(db) == 2
