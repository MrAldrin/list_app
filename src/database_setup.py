import os
import sqlite3


def init_database():
    db_path = os.environ.get("DB_PATH", "list.db")
    db = sqlite3.connect(db_path, check_same_thread=False)
    cursor = db.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS lists (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            list_tags TEXT NOT NULL DEFAULT '[]'
        )
        """
    )
    cursor.execute(
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
    cursor.execute("SELECT id FROM lists LIMIT 1")
    any_list = cursor.fetchone()
    if any_list is None:
        cursor.execute("INSERT INTO lists (name) VALUES (?)", ("default",))
        db.commit()
        default_list_id = cursor.lastrowid
    else:
        default_list_id = any_list[0]

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_items_list_done_name ON items(list_id, done, name)"
    )
    db.commit()

    return db, cursor, default_list_id


db, cursor, default_list_id = init_database()
