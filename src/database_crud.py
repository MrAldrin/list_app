import json
from database_setup import db, cursor


def normalize_item_name(raw: str | None) -> str:
    return (raw or "").strip().lower()


def get_lists():
    cursor.execute("SELECT id, name, enable_tags FROM lists ORDER BY name COLLATE NOCASE ASC")
    return cursor.fetchall()


def get_list_details(list_id: int):
    cursor.execute("SELECT id, name, enable_tags, list_tags FROM lists WHERE id = ?", (list_id,))
    row = cursor.fetchone()
    if not row:
        return None
    try:
        list_tags = json.loads(row[3]) if row[3] else []
    except json.JSONDecodeError:
        list_tags = []
    return {
        "id": row[0],
        "name": row[1],
        "enable_tags": bool(row[2]),
        "list_tags": list_tags
    }


def update_list_tags_settings(list_id: int, enable_tags: bool, list_tags: list[str]):
    cursor.execute(
        "UPDATE lists SET enable_tags = ?, list_tags = ? WHERE id = ?",
        (enable_tags, json.dumps(list_tags), list_id),
    )
    db.commit()


def update_item_active_tags(item_id: int, list_id: int, active_tags: list[str]):
    cursor.execute(
        "UPDATE items SET active_tags = ? WHERE id = ? AND list_id = ?",
        (json.dumps(active_tags), item_id, list_id),
    )
    db.commit()


def find_list_by_name(name: str):
    cursor.execute(
        "SELECT id FROM lists WHERE name = ? COLLATE NOCASE", (name,)
    )
    return cursor.fetchone()


def create_list(name: str, enable_tags: bool = False):
    normalized_name = normalize_item_name(name)
    if not normalized_name:
        raise ValueError("List name cannot be empty")
    existing = find_list_by_name(normalized_name)
    if existing:
        return existing[0]
    cursor.execute("INSERT INTO lists (name, enable_tags) VALUES (?, ?)", (normalized_name, enable_tags))
    db.commit()
    return cursor.lastrowid


def rename_list(list_id: int, new_name: str):
    cursor.execute(
        "UPDATE lists SET name = ? WHERE id = ?", (new_name, list_id)
    )
    db.commit()


def get_item_count(list_id: int) -> int:
    cursor.execute("SELECT COUNT(*) FROM items WHERE list_id = ?", (list_id,))
    return cursor.fetchone()[0]


def get_list_data(list_id: int):
    cursor.execute(
        "SELECT id, name, done, active_tags FROM items WHERE list_id = ? ORDER BY done ASC, name COLLATE NOCASE ASC",
        (list_id,),
    )
    rows = cursor.fetchall()
    list_items = []
    for r in rows:
        try:
            active_tags = json.loads(r[3]) if r[3] else []
        except json.JSONDecodeError:
            active_tags = []
        list_items.append({"id": r[0], "name": r[1], "done": bool(r[2]), "active_tags": active_tags})
    list_history_names = sorted(list(set(item["name"] for item in list_items)))
    return list_items, list_history_names


def find_item_by_name(list_id: int, item_name: str):
    cursor.execute(
        "SELECT id, done FROM items WHERE name = ? COLLATE NOCASE AND list_id = ?",
        (item_name, list_id),
    )
    return cursor.fetchone()


def restore_item(item_id: int, list_id: int):
    cursor.execute(
        "UPDATE items SET done = 0 WHERE id = ? AND list_id = ?",
        (item_id, list_id),
    )
    db.commit()


def add_item(item_name: str, list_id: int):
    cursor.execute(
        "INSERT INTO items (name, done, list_id) VALUES (?, ?, ?)",
        (item_name, False, list_id),
    )
    db.commit()


def update_item_done(item_id: int, list_id: int, done: bool):
    cursor.execute(
        "UPDATE items SET done = ? WHERE id = ? AND list_id = ?",
        (done, item_id, list_id),
    )
    db.commit()


def find_duplicate_name(list_id: int, item_id: int, new_name: str):
    cursor.execute(
        "SELECT id FROM items WHERE name = ? COLLATE NOCASE AND id != ? AND list_id = ?",
        (new_name, item_id, list_id),
    )
    return cursor.fetchone()


def rename_item(item_id: int, list_id: int, new_name: str):
    cursor.execute(
        "UPDATE items SET name = ? WHERE id = ? AND list_id = ?",
        (new_name, item_id, list_id),
    )
    db.commit()


def delete_item(item_id: int, list_id: int):
    cursor.execute(
        "DELETE FROM items WHERE id = ? AND list_id = ?",
        (item_id, list_id),
    )
    db.commit()


def delete_list(list_id: int):
    # First delete all items in the list
    cursor.execute("DELETE FROM items WHERE list_id = ?", (list_id,))
    # Then delete the list itself
    cursor.execute("DELETE FROM lists WHERE id = ?", (list_id,))
    db.commit()
