import os
import sqlite3


def init_database():
    db_path = os.environ.get("DB_PATH", "list.db")
    db = sqlite3.connect(db_path, check_same_thread=False)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS lists (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            list_tags TEXT NOT NULL DEFAULT '[]'
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY,
            name TEXT,
            done BOOLEAN,
            list_id INTEGER NOT NULL,
            active_tags TEXT NOT NULL DEFAULT '[]',
            FOREIGN KEY(list_id) REFERENCES lists(id)
        )
        """
    )

    # Ensure at least one list exists.
    any_list = db.execute("SELECT id FROM lists LIMIT 1").fetchone()
    if any_list is None:
        insert = db.execute("INSERT INTO lists (name) VALUES (?)", ("default",))
        db.commit()
        default_list_id = insert.lastrowid
    else:
        default_list_id = any_list[0]

    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_items_list_done_name ON items(list_id, done, name)"
    )
    db.commit()

    return db, default_list_id


db, default_list_id = init_database()
