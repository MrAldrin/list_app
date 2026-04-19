import os
import sqlite3


def init_database():
    db_path = os.environ.get("DB_PATH", "list.db")
    db = sqlite3.connect(db_path, check_same_thread=False)
    cursor = db.cursor()

    cursor.execute(
        "CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT, done BOOLEAN)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS lists (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)"
    )

    # Step migration: add list_id to existing items table when missing.
    cursor.execute("PRAGMA table_info(items)")
    item_columns = [row[1] for row in cursor.fetchall()]
    if "list_id" not in item_columns:
        cursor.execute("ALTER TABLE items ADD COLUMN list_id INTEGER")
        db.commit()

    # Step migration: ensure a default list exists and backfill existing items.
    cursor.execute("SELECT id FROM lists WHERE name = ?", ("default",))
    default_list = cursor.fetchone()
    if default_list is None:
        cursor.execute("INSERT INTO lists (name) VALUES (?)", ("default",))
        db.commit()
        default_list_id = cursor.lastrowid
    else:
        default_list_id = default_list[0]

    cursor.execute(
        "UPDATE items SET list_id = ? WHERE list_id IS NULL",
        (default_list_id,),
    )
    db.commit()

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_items_list_done_name ON items(list_id, done, name)"
    )
    db.commit()

    return db, cursor, default_list_id


db, cursor, default_list_id = init_database()
