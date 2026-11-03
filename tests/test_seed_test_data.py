"""The seed script fills a test database once with sample data."""

import seed_test_data as script

from database_setup import db


def _count(table: str) -> int:
    return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_seed_adds_rooms_lists_and_items_once():
    lists_before = _count("lists")

    assert script.seed() is True
    sample_lists = sum(len(lists) for lists in script.SAMPLE_DATA.values())
    sample_items = sum(
        len(spec.items)
        for lists in script.SAMPLE_DATA.values()
        for spec in lists.values()
    )
    assert _count("rooms") == 2
    assert _count("lists") == lists_before + sample_lists
    assert _count("items") == sample_items

    assert script.seed() is False
    assert _count("items") == sample_items


def test_seed_sets_quantity_tags_and_checked():
    script.seed()
    row = db.execute(
        "SELECT i.quantity, i.active_tags, i.done FROM items AS i "
        "JOIN lists AS l ON l.id = i.list_id JOIN rooms AS r ON r.id = l.room_id "
        "WHERE r.name = 'Home' AND i.name = 'milk'"
    ).fetchone()
    assert row == (2, '["ICA"]', 0)
    done = db.execute(
        "SELECT i.done FROM items AS i JOIN lists AS l ON l.id = i.list_id "
        "JOIN rooms AS r ON r.id = l.room_id "
        "WHERE r.name = 'Home' AND i.name = 'bananas'"
    ).fetchone()
    assert done == (1,)


def test_seed_pins_fixed_room_codes_on_every_run():
    script.seed()
    codes = dict(db.execute("SELECT name, slug FROM rooms").fetchall())
    assert codes == {"Home": "home-test", "Cabin": "cabin-test"}

    # A rerun on an existing database puts the codes back.
    db.execute("UPDATE rooms SET slug = 'cabin-123456' WHERE name = 'Cabin'")
    db.commit()
    assert script.seed() is False
    assert db.execute("SELECT slug FROM rooms WHERE name = 'Cabin'").fetchone() == (
        "cabin-test",
    )


def test_seed_dates_are_relative_to_today():
    from datetime import date

    script.seed(today=date(2026, 11, 3))
    dates = dict(
        db.execute(
            "SELECT i.name, i.date FROM items AS i JOIN lists AS l ON l.id = i.list_id "
            "WHERE l.name = 'Due dates'"
        ).fetchall()
    )
    assert dates["pay the electricity bill"] == "2026-10-29"
    assert dates["dentist appointment"] == "2026-11-03"
    assert dates["buy a birthday gift"] == "2026-11-04"
    assert dates["call the plumber"] is None


def test_seed_sets_add_counts_tag_colors_and_settings():
    script.seed()
    cabin_list = (
        "SELECT {} FROM lists AS l JOIN rooms AS r ON r.id = l.room_id "
        "WHERE r.name = 'Cabin' AND l.name = ?"
    )
    assert db.execute(cabin_list.format("l.tag_mode"), ("Packing",)).fetchone() == (
        "single",
    )
    assert db.execute(
        cabin_list.format("l.hide_done_mode"), ("Cabin chores",)
    ).fetchone() == ("recent",)
    colors = db.execute(cabin_list.format("l.tag_colors"), ("Groceries",)).fetchone()
    assert colors == ('{"ICA": 2, "Lidl": 0, "Coop": 1}',)
    counts = db.execute(
        "SELECT i.add_count FROM items AS i JOIN lists AS l ON l.id = i.list_id "
        "JOIN rooms AS r ON r.id = l.room_id "
        "WHERE r.name = 'Cabin' AND l.name = 'Groceries' AND i.name = 'milk'"
    ).fetchone()
    assert counts == (9,)
