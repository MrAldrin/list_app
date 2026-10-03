import sqlite3

from database_setup import _migration_1_baseline, init_database
from migrations import run_migrations


def test_additive_invitation_migration_preserves_existing_rows(tmp_path, monkeypatch):
    path = tmp_path / "migration.db"
    monkeypatch.setenv("DB_PATH", str(path))
    # Build the schema as it was before versioned migrations (the baseline);
    # later migrations add columns that a version 0 database never had.
    connection = sqlite3.connect(path)
    run_migrations(connection, [lambda db: _migration_1_baseline(db, "pw")])
    room_id = connection.execute("SELECT id FROM rooms").fetchone()[0]
    connection.execute(
        "INSERT INTO lists (id, name, slug, room_id, share_token) "
        "VALUES (1, 'Shop', 'shop', ?, 'existing-share-token')",
        (room_id,),
    )
    connection.execute("INSERT INTO items (name, list_id) VALUES ('Milk', 1)")
    connection.execute(
        "INSERT INTO room_access_tokens (token_hash, room_id, authorization_version) "
        "VALUES ('existing-hash', ?, 1)",
        (room_id,),
    )
    connection.execute("DROP TABLE room_invitations")
    # Simulate a database from before versioned migrations.
    connection.execute("PRAGMA user_version = 0")
    connection.commit()
    tables = ("rooms", "lists", "items", "room_access_tokens")
    columns = {
        table: [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
        for table in tables
    }
    before = {
        table: connection.execute(
            f"SELECT {', '.join(columns[table])} FROM {table}"
        ).fetchall()
        for table in tables
    }
    connection.close()
    for _ in range(2):
        connection = init_database()
        for table in tables:
            assert (
                connection.execute(
                    f"SELECT {', '.join(columns[table])} FROM {table}"
                ).fetchall()
                == before[table]
            )
        assert connection.execute("SELECT * FROM room_invitations").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        connection.close()
