"""Fill a test database with sample rooms, lists and items.

Usage:
    DB_PATH=/path/to/test.db uv run python scripts/seed_test_data.py

`serve_svelte_local.py --seed` runs this for you. Adds the lists to `Home`
(password APP_PASSWORD) and creates a `Cabin` room (password `cabin`).
Running it again changes nothing once `Cabin` exists.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import database_crud as crud
from database_setup import db

SEED_ROOM = "Cabin"
SEED_ROOM_PASSWORD = "cabin"

# Item: (name, quantity, description, tags, checked)
Item = tuple[str, int | None, str, list[str], bool]

# Room name -> list name -> (list tags, items).
SAMPLE_DATA: dict[str, dict[str, tuple[list[str], list[Item]]]] = {
    "Home": {
        "Groceries": (
            ["ICA", "Lidl"],
            [
                ("milk", 2, "", ["ICA"], False),
                ("bread", None, "Rye, sliced", [], False),
                ("eggs", 12, "", ["Lidl"], False),
                ("cheese", None, "", ["ICA"], False),
                ("bananas", 6, "", [], True),
                ("coffee", None, "Dark roast", ["Lidl"], True),
            ],
        ),
        "Hardware store": (
            [],
            [
                ("light bulbs", 3, "E27, warm white", [], False),
                ("wood screws", None, "4x40 mm", [], False),
                ("paint roller", None, "", [], True),
            ],
        ),
        "Things to fix around the house before the summer holidays start": (
            [],
            [
                ("kitchen tap drips", None, "", [], False),
                ("squeaky bedroom door", None, "", [], False),
                ("replace the broken tile in the hallway", None, "", [], False),
            ],
        ),
    },
    SEED_ROOM: {
        "Packing": (
            ["Clothes", "Gear"],
            [
                ("rain jacket", None, "", ["Clothes"], False),
                ("wool socks", 4, "", ["Clothes"], False),
                ("headlamp", None, "Check the batteries", ["Gear"], False),
                ("sleeping bag", 2, "", ["Gear"], True),
            ],
        ),
        "Food for the trip": (
            [],
            [
                ("pasta", 2, "", [], False),
                ("tomato sauce", 2, "", [], False),
                ("oat milk", None, "", [], True),
            ],
        ),
        "Cabin chores": (
            [],
            [
                ("chop firewood", None, "", [], False),
                ("empty the water tank", None, "Before leaving", [], False),
            ],
        ),
    },
}


def _room_id(name: str) -> int:
    """The room's ID, creating it if it does not exist."""
    with crud.transaction():
        row = db.execute("SELECT id FROM rooms WHERE name = ?", (name,)).fetchone()
    if row:
        return row[0]
    room_id, _slug = crud.create_room(name, SEED_ROOM_PASSWORD)
    return room_id


def _add_list(room_id: int, name: str, tags: list[str], items: list[Item]) -> None:
    list_id, _slug, _created = crud.create_or_find_list_locked(name, room_id)
    for tag in tags:
        crud.change_list_tag_locked(list_id, tag, add=True)
    for item_name, quantity, description, item_tags, checked in items:
        _status, item_id = crud.add_or_restore_item_locked(item_name, list_id)
        crud.update_item_details_locked(
            item_id, list_id, item_name, description, quantity
        )
        for tag in item_tags:
            crud.toggle_item_active_tag_locked(item_id, list_id, tag, active=True)
        if checked:
            crud.update_item_done_locked(item_id, list_id, True)


def seed() -> bool:
    """Add the sample data; False if it was there already."""
    with crud.transaction():
        if db.execute("SELECT 1 FROM rooms WHERE name = ?", (SEED_ROOM,)).fetchone():
            return False
    for room_name, lists in SAMPLE_DATA.items():
        room_id = _room_id(room_name)
        with crud.transaction(write=True):
            for list_name, (tags, items) in lists.items():
                _add_list(room_id, list_name, tags, items)
    return True


if __name__ == "__main__":
    if seed():
        print(f"Added sample data. {SEED_ROOM} password: {SEED_ROOM_PASSWORD}")
    else:
        print("Sample data is there already; nothing changed.")
