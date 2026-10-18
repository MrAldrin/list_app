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
        len(items)
        for lists in script.SAMPLE_DATA.values()
        for _tags, items in lists.values()
    )
    assert _count("rooms") == 2
    assert _count("lists") == lists_before + sample_lists
    assert _count("items") == sample_items

    assert script.seed() is False
    assert _count("items") == sample_items


def test_seed_sets_quantity_tags_and_checked():
    script.seed()
    row = db.execute(
        "SELECT quantity, active_tags, done FROM items WHERE name = 'milk'"
    ).fetchone()
    assert row == (2, '["ICA"]', 0)
    done = db.execute("SELECT done FROM items WHERE name = 'bananas'").fetchone()
    assert done == (1,)
