import os
import re
import sqlite3
import uuid

import bcrypt
from dotenv import load_dotenv

# Load env variables so we can use APP_PASSWORD for default room migration if run directly
load_dotenv()


def init_database():
    db_path = os.environ.get("DB_PATH", "list.db")
    db = sqlite3.connect(db_path, check_same_thread=False)
    
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE,
            password_hash TEXT NOT NULL
        )
        """
    )

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

    # Migration: Check if room_id exists in lists table
    if "room_id" not in columns:
        db.execute("ALTER TABLE lists ADD COLUMN room_id INTEGER")
        
        global_pw = os.environ.get("APP_PASSWORD", "dev_password")
        pw_hash = bcrypt.hashpw(global_pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        short_uuid = str(uuid.uuid4())[:6]
        default_room_slug = f"home-{short_uuid}"
        
        existing_room = db.execute("SELECT id FROM rooms WHERE name = 'Home'").fetchone()
        if existing_room:
            default_room_id = existing_room[0]
        else:
            insert = db.execute(
                "INSERT INTO rooms (name, slug, password_hash) VALUES (?, ?, ?)",
                ("Home", default_room_slug, pw_hash)
            )
            default_room_id = insert.lastrowid
            
        # Backfill existing lists to belong to this room
        db.execute("UPDATE lists SET room_id = ? WHERE room_id IS NULL", (default_room_id,))
        db.commit()

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
        any_room = db.execute("SELECT id FROM rooms LIMIT 1").fetchone()
        if any_room:
            room_id = any_room[0]
        else:
            global_pw = os.environ.get("APP_PASSWORD", "dev_password")
            pw_hash = bcrypt.hashpw(global_pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            short_uuid_room = str(uuid.uuid4())[:6]
            room_slug = f"home-{short_uuid_room}"
            insert_room = db.execute(
                "INSERT INTO rooms (name, slug, password_hash) VALUES (?, ?, ?)",
                ("Home", room_slug, pw_hash)
            )
            room_id = insert_room.lastrowid
            
        short_uuid_list = str(uuid.uuid4())[:6]
        list_slug = f"default-{short_uuid_list}"
        insert = db.execute("INSERT INTO lists (name, slug, room_id) VALUES (?, ?, ?)", ("default", list_slug, room_id))
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
