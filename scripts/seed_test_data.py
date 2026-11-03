"""Fill a test database with sample rooms, lists and items, ready for testing.

Usage:
    DB_PATH=/path/to/test.db uv run python scripts/seed_test_data.py

`serve_svelte_local.py --seed` runs this for you. It gives `Home` (password
APP_PASSWORD) and `Cabin` (password `cabin`) fixed room codes, `home-test` and
`cabin-test`, so a browser that remembers them keeps working with a new test
database. `Cabin` gets lists that exercise most features: dates for the
reminders (relative to today), tags with colors, both tag modes, add counts and
add times for sorting and usual items, checked items, a hide-done setting, a
long list and an empty list.

The room codes are set on every run. The sample data is added only once, while
`Cabin` does not exist; dates are relative to the day it is added, so start a
fresh database (`serve_svelte_local.py --fresh --seed`) on another day.
"""

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import database_crud as crud
from database_setup import db

SEED_ROOM = "Cabin"
SEED_ROOM_PASSWORD = "cabin"

# Fixed room codes, so a remembered room still opens after a new test database.
ROOM_CODES = {"Home": "home-test", SEED_ROOM: "cabin-test"}


class Item(NamedTuple):
    name: str
    quantity: int | None = None
    description: str = ""
    tags: tuple[str, ...] = ()
    checked: bool = False
    # Days from today: negative is overdue, 0 today, None no date.
    due_in_days: int | None = None
    # Times added (shown as "Added 3 times"; usual items need 2 or more).
    add_count: int = 1
    # Last added this many hours ago, for the "Added" sort.
    added_hours_ago: int = 0


class ListSpec(NamedTuple):
    tags: tuple[str, ...]
    items: tuple[Item, ...]
    # (tag name, color index 0-6) pairs.
    colors: tuple[tuple[str, int], ...] = ()
    tag_mode: str = "multi"
    # (mode, age_days, recent_count) for hide-done, or None for the default.
    hide_done: tuple[str, int, int] | None = None


_BIG_SHOP_NAMES = (
    "apples avocados bacon basil beans broccoli butter carrots cereal chicken "
    "chocolate cream cucumber dish soap flour garlic ginger honey ketchup "
    "lemons lettuce mushrooms mustard noodles olive oil onions oranges peanut "
    "butter peppers potatoes rice salmon salt spinach sugar tea toilet paper "
    "tortillas tuna vinegar"
)


def _big_shop_items() -> tuple[Item, ...]:
    """About 40 items with different counts and add times, some checked."""
    words = _BIG_SHOP_NAMES.split()
    # Join the two-word names back together.
    names: list[str] = []
    skip = False
    for index, word in enumerate(words):
        if skip:
            skip = False
            continue
        if word in {"dish", "olive", "peanut", "toilet"}:
            names.append(f"{word} {words[index + 1]}")
            skip = True
        else:
            names.append(word)
    return tuple(
        Item(
            name,
            quantity=(index % 4) + 1 if index % 3 == 0 else None,
            checked=index % 5 == 4,
            add_count=(index * 7) % 11 + 1,
            added_hours_ago=(index * 13) % 200,
            due_in_days=5 if index == 7 else None,
        )
        for index, name in enumerate(names)
    )


# Room name -> list name -> list.
SAMPLE_DATA: dict[str, dict[str, ListSpec]] = {
    "Home": {
        "Groceries": ListSpec(
            ("ICA", "Lidl"),
            (
                Item("milk", 2, tags=("ICA",)),
                Item("bread", description="Rye, sliced"),
                Item("eggs", 12, tags=("Lidl",)),
                Item("cheese", tags=("ICA",)),
                Item("bananas", 6, checked=True),
                Item("coffee", description="Dark roast", tags=("Lidl",), checked=True),
            ),
        ),
        "Hardware store": ListSpec(
            (),
            (
                Item("light bulbs", 3, "E27, warm white"),
                Item("wood screws", description="4x40 mm"),
                Item("paint roller", checked=True),
            ),
        ),
        "Things to fix around the house before the summer holidays start": ListSpec(
            (),
            (
                Item("kitchen tap drips"),
                Item("squeaky bedroom door"),
                Item("replace the broken tile in the hallway"),
            ),
        ),
    },
    SEED_ROOM: {
        # Tags (several per item) with colors, dates, add counts and checked items.
        "Groceries": ListSpec(
            ("ICA", "Lidl", "Coop"),
            (
                Item("milk", 2, tags=("ICA",), due_in_days=0, add_count=9),
                Item("bread", description="Rye, sliced", due_in_days=1, add_count=6),
                Item("eggs", 12, tags=("Lidl",), add_count=4, added_hours_ago=30),
                Item(
                    "cheese", tags=("ICA", "Coop"), due_in_days=-2, added_hours_ago=60
                ),
                Item("tomatoes", 4, tags=("Coop",), added_hours_ago=5),
                Item("yoghurt", tags=("ICA",), due_in_days=4, added_hours_ago=12),
                Item("pasta", 2, added_hours_ago=90),
                Item("butter", tags=("ICA",), checked=True, add_count=7),
                Item(
                    "coffee",
                    description="Dark roast",
                    tags=("Lidl",),
                    checked=True,
                    add_count=5,
                ),
                Item("bananas", 6, checked=True, add_count=3, added_hours_ago=48),
                Item("oat milk", checked=True, add_count=2, added_hours_ago=72),
            ),
            colors=(("ICA", 2), ("Lidl", 0), ("Coop", 1)),
        ),
        # Every kind of due date, for the reminders.
        "Due dates": ListSpec(
            (),
            (
                Item("pay the electricity bill", due_in_days=-5),
                Item("return library books", due_in_days=-1),
                Item("dentist appointment", description="10:30", due_in_days=0),
                Item("buy a birthday gift", due_in_days=1),
                Item("renew passport", due_in_days=3),
                Item("book a car service", due_in_days=10),
                Item("call the plumber"),
                Item("old overdue task (checked)", checked=True, due_in_days=-3),
            ),
        ),
        # One tag per item, with colors.
        "Packing": ListSpec(
            ("Clothes", "Gear", "Food"),
            (
                Item("rain jacket", tags=("Clothes",)),
                Item("wool socks", 4, tags=("Clothes",)),
                Item(
                    "headlamp",
                    description="Check the batteries",
                    tags=("Gear",),
                    due_in_days=1,
                ),
                Item("trail mix", 3, tags=("Food",)),
                Item("map"),
                Item("sleeping bag", 2, tags=("Gear",), checked=True),
            ),
            colors=(("Clothes", 4), ("Gear", 5), ("Food", 3)),
            tag_mode="single",
        ),
        # Hides checked items except the two most recent.
        "Cabin chores": ListSpec(
            (),
            (
                Item("chop firewood", due_in_days=0),
                Item("empty the water tank", description="Before leaving"),
                Item("sweep the porch", checked=True),
                Item("clean the stove", checked=True),
                Item("fix the gate", checked=True),
            ),
            hide_done=("recent", 30, 2),
        ),
        # Long enough to scroll; varied counts and add times for every sort.
        "Big shop": ListSpec((), _big_shop_items()),
        "Empty list": ListSpec((), ()),
    },
}


def _iso_hours_ago(hours: int) -> str:
    stamp = datetime.now(UTC) - timedelta(hours=hours)
    return stamp.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _room_id(name: str) -> int:
    """The room's ID, creating it if it does not exist."""
    with crud.transaction():
        row = db.execute("SELECT id FROM rooms WHERE name = ?", (name,)).fetchone()
    if row:
        return row[0]
    room_id, _slug = crud.create_room(name, SEED_ROOM_PASSWORD)
    return room_id


def _add_list(room_id: int, name: str, spec: ListSpec, today: date) -> None:
    list_id, _slug, _created = crud.create_or_find_list_locked(name, room_id)
    for tag in spec.tags:
        crud.change_list_tag_locked(list_id, tag, add=True)
    for tag, color in spec.colors:
        crud.set_list_tag_color_locked(list_id, tag, color)
    if spec.tag_mode != "multi":
        crud.update_list_tag_settings_locked(list_id, mode=spec.tag_mode)
    if spec.hide_done is not None:
        mode, age_days, recent_count = spec.hide_done
        crud.update_list_visibility_settings_locked(
            list_id, mode=mode, age_days=age_days, recent_count=recent_count
        )
    for item in spec.items:
        _status, item_id = crud.add_or_restore_item_locked(item.name, list_id)
        due = (
            None
            if item.due_in_days is None
            else (today + timedelta(days=item.due_in_days)).isoformat()
        )
        crud.update_item_details_locked(
            item_id,
            list_id,
            item.name,
            item.description,
            item.quantity,
            date_given=due is not None,
            date=due,
        )
        for tag in item.tags:
            crud.toggle_item_active_tag_locked(item_id, list_id, tag, active=True)
        db.execute(
            "UPDATE items SET add_count = ?, added_at = ? WHERE id = ?",
            (item.add_count, _iso_hours_ago(item.added_hours_ago), item_id),
        )
        if item.checked:
            crud.update_item_done_locked(item_id, list_id, True)


def pin_room_codes() -> None:
    """Give the sample rooms their fixed codes (`ROOM_CODES`), if they exist."""
    with crud.transaction(write=True):
        for name, code in ROOM_CODES.items():
            db.execute(
                "UPDATE rooms SET slug = ? WHERE name = ? AND slug != ?",
                (code, name, code),
            )


def seed(today: date | None = None) -> bool:
    """Add the sample data and pin the room codes; False if the data was there."""
    today = date.today() if today is None else today
    with crud.transaction():
        exists = db.execute(
            "SELECT 1 FROM rooms WHERE name = ?", (SEED_ROOM,)
        ).fetchone()
    if not exists:
        for room_name, lists in SAMPLE_DATA.items():
            room_id = _room_id(room_name)
            with crud.transaction(write=True):
                for list_name, spec in lists.items():
                    _add_list(room_id, list_name, spec, today)
    pin_room_codes()
    return not exists


if __name__ == "__main__":
    if seed():
        print(f"Added sample data. {SEED_ROOM} password: {SEED_ROOM_PASSWORD}")
    else:
        print("Sample data is there already; room codes checked.")
