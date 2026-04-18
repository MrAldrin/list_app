from database import db, cursor


def normalize_item_name(raw: str | None) -> str:
    return (raw or "").strip().lower()


def get_lists():
    cursor.execute("SELECT id, name FROM lists ORDER BY name COLLATE NOCASE ASC")
    return cursor.fetchall()


def create_list(name: str):
    normalized_name = normalize_item_name(name)
    if not normalized_name:
        raise ValueError("List name cannot be empty")
    cursor.execute("SELECT id FROM lists WHERE name = ? COLLATE NOCASE", (normalized_name,))
    existing = cursor.fetchone()
    if existing:
        return existing[0]
    cursor.execute("INSERT INTO lists (name) VALUES (?)", (normalized_name,))
    db.commit()
    return cursor.lastrowid


def get_list_data(list_id: int):
    cursor.execute(
        "SELECT id, name, done FROM items WHERE list_id = ? ORDER BY done ASC, name COLLATE NOCASE ASC",
        (list_id,),
    )
    rows = cursor.fetchall()
    list_items = [{"id": r[0], "name": r[1], "done": bool(r[2])} for r in rows]
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
