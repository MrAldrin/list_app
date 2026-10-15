"""Quantity buttons apply deltas to current storage, not rendered snapshots."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from api_helpers import (
    create_list,
    find_item_by_name,
    get_list_data,
    insert_item,
    write_locked,
)

from database_crud import adjust_item_quantity, adjust_item_quantity_locked, get_rooms
from database_setup import db


@pytest.fixture
def quantity_item():
    list_id, slug = create_list("quantities", get_rooms()[0]["id"])
    insert_item("milk", list_id)
    item_id = find_item_by_name(list_id, "milk")[0]
    return list_id, slug, item_id


def stored_quantity(list_id):
    return get_list_data(list_id)[0][0]["quantity"]


@pytest.mark.parametrize(
    "initial, deltas, expected",
    [
        (1, [1, 1], 3),
        (10, [-1, -1], 8),
        (10, [1, -1, 1, -1], 10),
        (1, [-1, -1], 1),
        (2, [-1, -1, -1, -1], 1),
        (1, [1] * 20, 21),
    ],
)
def test_concurrent_quantity_changes(quantity_item, initial, deltas, expected):
    list_id, _, item_id = quantity_item
    db.execute("UPDATE items SET quantity = ? WHERE id = ?", (initial, item_id))
    db.commit()
    # All clients saw the same old value before sending their button changes.
    assert stored_quantity(list_id) == initial
    barrier = Barrier(len(deltas))

    def change(delta):
        barrier.wait(timeout=10)
        return write_locked(adjust_item_quantity_locked, item_id, list_id, delta)

    with ThreadPoolExecutor(max_workers=len(deltas)) as executor:
        assert all(executor.map(change, deltas))

    assert stored_quantity(list_id) == expected
    assert not db.in_transaction


@pytest.mark.parametrize("delta, expected", [(1, 2), (-1, 1)])
def test_legacy_null_quantity_uses_display_default(
    quantity_item, delta, expected, without_field_rules
):
    list_id, slug, item_id = quantity_item
    db.execute("UPDATE items SET quantity = NULL WHERE id = ?", (item_id,))
    db.commit()
    adjust_item_quantity(item_id, list_id, delta, expected_slug=slug)
    assert stored_quantity(list_id) == expected


def test_quantity_change_is_scoped_to_list(quantity_item):
    list_id, _, item_id = quantity_item
    other_id, other_slug = create_list("other", get_rooms()[0]["id"])
    adjust_item_quantity(item_id, other_id, 1, expected_slug=other_slug)
    assert stored_quantity(list_id) == 1
