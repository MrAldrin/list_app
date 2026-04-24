import os
import re
import sqlite3
import uuid


def init_database():
    db_path = os.environ.get("DB_PATH", "list.db")
    db = sqlite3.connect(db_path, check_same_thread=False)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS lists (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            list_tags TEXT NOT NULL DEFAULT '[]',
            slug TEXT UNIQUE
        )
        """
    )
    
    # Migration: Check if slug exists in lists table
    cursor = db.execute("PRAGMA table_info(lists)")
    columns = [col[1] for col in cursor.fetchall()]
    if "slug" not in columns:
        db.execute("ALTER TABLE lists ADD COLUMN slug TEXT")
        
        # Backfill existing lists with slugs
        rows = db.execute("SELECT id, name FROM lists WHERE slug IS NULL").fetchall()
        for row in rows:
            list_id, name = row
            safe_name = re.sub(r'[^a-z0-9]', '-', name.lower().strip())
            short_uuid = str(uuid.uuid4())[:6]
            slug = f"{safe_name}-{short_uuid}"
            db.execute("UPDATE lists SET slug = ? WHERE id = ?", (slug, list_id))
        db.commit()
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_lists_slug ON lists(slug)")
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
