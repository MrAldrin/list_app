from database_setup import init_database


def test_additive_invitation_migration_preserves_existing_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "migration.db"))
    connection = init_database()
    room_id = connection.execute("SELECT id FROM rooms").fetchone()[0]
    connection.execute(
        "INSERT INTO lists (id, name, slug, room_id) VALUES (1, 'Shop', 'shop', ?)",
        (room_id,),
    )
    connection.execute("INSERT INTO items (name, list_id) VALUES ('Milk', 1)")
    connection.execute(
        "INSERT INTO room_access_tokens (token_hash, room_id, authorization_version) "
        "VALUES ('existing-hash', ?, 1)",
        (room_id,),
    )
    connection.execute("DROP TABLE room_invitations")
    connection.commit()
    tables = ("rooms", "lists", "items", "room_access_tokens")
    before = {
        table: connection.execute(f"SELECT * FROM {table}").fetchall()
        for table in tables
    }
    connection.close()
    for _ in range(2):
        connection = init_database()
        for table in tables:
            assert (
                connection.execute(f"SELECT * FROM {table}").fetchall() == before[table]
            )
        assert connection.execute("SELECT * FROM room_invitations").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        connection.close()
