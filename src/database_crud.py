import json
import re
import threading
import uuid

from database_setup import db

_DB_LOCK = threading.RLock()


def normalize_item_name(raw: str | None) -> str:
    return (raw or "").strip().lower()


def get_lists():
    with _DB_LOCK:
        rows = db.execute("SELECT id, name, slug FROM lists ORDER BY name COLLATE NOCASE ASC").fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def get_list_details(list_id: int):
    with _DB_LOCK:
        row = db.execute(
            "SELECT id, name, list_tags, slug FROM lists WHERE id = ?", (list_id,)
        ).fetchone()
    if not row:
        return None
    try:
        list_tags = json.loads(row[2]) if row[2] else []
    except json.JSONDecodeError:
        list_tags = []
    return {"id": row[0], "name": row[1], "list_tags": list_tags, "slug": row[3]}


def update_list_tags_settings(list_id: int, list_tags: list[str]):
    with _DB_LOCK:
        db.execute(
            "UPDATE lists SET list_tags = ? WHERE id = ?",
            (json.dumps(list_tags), list_id),
        )
        db.commit()


def update_item_active_tags(item_id: int, list_id: int, active_tags: list[str]):
    with _DB_LOCK:
        db.execute(
            "UPDATE items SET active_tags = ? WHERE id = ? AND list_id = ?",
            (json.dumps(active_tags), item_id, list_id),
        )
        db.commit()


def find_list_by_name(name: str):
    with _DB_LOCK:
        result = db.execute("SELECT id FROM lists WHERE name = ? COLLATE NOCASE", (name,))
        return result.fetchone()


def create_list(name: str):
    normalized_name = normalize_item_name(name)
    if not normalized_name:
        raise ValueError("List name cannot be empty")

    with _DB_LOCK:
        existing = db.execute(
            "SELECT id FROM lists WHERE name = ? COLLATE NOCASE", (normalized_name,)
        ).fetchone()
        if existing:
            return existing[0]

        safe_name = re.sub(r'[^a-z0-9]', '-', name.lower().strip())
        short_uuid = str(uuid.uuid4())[:6]
        slug = f"{safe_name}-{short_uuid}"

        result = db.execute("INSERT INTO lists (name, slug) VALUES (?, ?)", (normalized_name, slug))
        db.commit()
        return result.lastrowid


def rename_list(list_id: int, new_name: str):
    with _DB_LOCK:
        db.execute("UPDATE lists SET name = ? WHERE id = ?", (new_name, list_id))
        db.commit()


def get_item_count(list_id: int) -> int:
    with _DB_LOCK:
        row = db.execute("SELECT COUNT(*) FROM items WHERE list_id = ?", (list_id,)).fetchone()
    return row[0]


def get_list_data(list_id: int):
    with _DB_LOCK:
        rows = db.execute(
            (
                "SELECT id, name, done, active_tags FROM items "
                "WHERE list_id = ? ORDER BY done ASC, name COLLATE NOCASE ASC"
            ),
            (list_id,),
        ).fetchall()

    list_items = []
    for r in rows:
        try:
            active_tags = json.loads(r[3]) if r[3] else []
        except json.JSONDecodeError:
            active_tags = []
        list_items.append(
            {"id": r[0], "name": r[1], "done": bool(r[2]), "active_tags": active_tags}
        )

    list_history_names = sorted(list(set(item["name"] for item in list_items)))
    return list_items, list_history_names


def find_item_by_name(list_id: int, item_name: str):
    with _DB_LOCK:
        result = db.execute(
            "SELECT id, done FROM items WHERE name = ? COLLATE NOCASE AND list_id = ?",
            (item_name, list_id),
        )
        return result.fetchone()


def restore_item(item_id: int, list_id: int):
    with _DB_LOCK:
        db.execute(
            "UPDATE items SET done = 0 WHERE id = ? AND list_id = ?",
            (item_id, list_id),
        )
        db.commit()


def add_item(item_name: str, list_id: int):
    with _DB_LOCK:
        db.execute(
            "INSERT INTO items (name, done, list_id) VALUES (?, ?, ?)",
            (item_name, False, list_id),
        )
        db.commit()


def add_item_with_state(item_name: str, list_id: int, done: bool, active_tags: list[str]):
    with _DB_LOCK:
        db.execute(
            "INSERT INTO items (name, done, list_id, active_tags) VALUES (?, ?, ?, ?)",
            (item_name, done, list_id, json.dumps(active_tags)),
        )
        db.commit()


def update_item_done(item_id: int, list_id: int, done: bool):
    with _DB_LOCK:
        db.execute(
            "UPDATE items SET done = ? WHERE id = ? AND list_id = ?",
            (done, item_id, list_id),
        )
        db.commit()


def find_duplicate_name(list_id: int, item_id: int, new_name: str):
    with _DB_LOCK:
        result = db.execute(
            "SELECT id FROM items WHERE name = ? COLLATE NOCASE AND id != ? AND list_id = ?",
            (new_name, item_id, list_id),
        )
        return result.fetchone()


def rename_item(item_id: int, list_id: int, new_name: str):
    with _DB_LOCK:
        db.execute(
            "UPDATE items SET name = ? WHERE id = ? AND list_id = ?",
            (new_name, item_id, list_id),
        )
        db.commit()


def delete_item(item_id: int, list_id: int):
    with _DB_LOCK:
        db.execute(
            "DELETE FROM items WHERE id = ? AND list_id = ?",
            (item_id, list_id),
        )
        db.commit()


def delete_list(list_id: int):
    with _DB_LOCK:
        # First delete all items in the list
        db.execute("DELETE FROM items WHERE list_id = ?", (list_id,))
        # Then delete the list itself
        db.execute("DELETE FROM lists WHERE id = ?", (list_id,))
        db.commit()
