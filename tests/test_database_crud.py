from concurrent.futures import ThreadPoolExecutor

import pytest
from database_crud import (
    normalize_item_name,
    get_lists,
    create_list,
    create_room,
    get_list_data,
    find_item_by_name,
    restore_item,
    add_item,
    update_item_done,
    find_duplicate_name,
    rename_item,
    delete_item,
    find_list_by_name,
    rename_list,
    delete_list,
)


@pytest.fixture
def room_id():
    room_id_value, _ = create_room("Test Room", "pw")
    return room_id_value


def test_normalize_item_name():
    # Verify that raw item names are correctly stripped, lowercased, and handle None.
    assert normalize_item_name(raw="  Apples  ") == "apples"
    assert normalize_item_name(raw=None) == ""
    assert normalize_item_name(raw="\nBREAD\t") == "bread"


def test_create_list_success(room_id):
    # Verify that a new list can be created and is included in the list of all lists.
    list_id, _ = create_list(name="Groceries", room_id=room_id)
    assert list_id is not None
    lists = get_lists(room_id)
    assert len(lists) == 1
    assert any(entry[1] == "groceries" for entry in lists)


def test_create_list_duplicate(room_id):
    # Verify that creating a list with a name that already exists returns the existing ID.
    create_list(name="Groceries", room_id=room_id)
    # This should return the same ID and not create a new row
    create_list(name="GROCERIES", room_id=room_id)
    lists = get_lists(room_id)
    assert len([entry for entry in lists if entry[1] == "groceries"]) == 1


def test_create_list_empty(room_id):
    # Verify that creating a list with an empty or whitespace-only name raises a ValueError.
    with pytest.raises(
        expected_exception=ValueError, match="List name cannot be empty"
    ):
        create_list(name="", room_id=room_id)
    with pytest.raises(
        expected_exception=ValueError, match="List name cannot be empty"
    ):
        create_list(name="   ", room_id=room_id)


def test_add_and_get_items(room_id):
    # Verify that items can be added to a list and retrieved with correct sorting and history.
    list_id, _ = create_list(name="My List", room_id=room_id)
    add_item(item_name="Apples", list_id=list_id)
    add_item(item_name="Bananas", list_id=list_id)

    items, history = get_list_data(list_id=list_id)
    assert len(items) == 2
    assert history == ["Apples", "Bananas"]
    # items should be sorted by done ASC, name COLLATE NOCASE ASC
    assert items[0]["name"] == "Apples"
    assert items[0]["done"] is False
    assert items[1]["name"] == "Bananas"
    assert items[1]["done"] is False


def test_find_item_by_name(room_id):
    # Verify that an item can be found by its name within a specific list.
    list_id, _ = create_list(name="My List", room_id=room_id)
    add_item(item_name="Apples", list_id=list_id)

    item = find_item_by_name(list_id=list_id, item_name="apples")
    assert item is not None
    assert item[1] == 0  # done=False

    assert find_item_by_name(list_id=list_id, item_name="nonexistent") is None
    # Check that it's list-specific
    other_list_id, _ = create_list(name="Other List", room_id=room_id)
    assert find_item_by_name(list_id=other_list_id, item_name="apples") is None


def test_update_item_done(room_id):
    # Verify that an item's completion status can be updated.
    list_id, _ = create_list(name="My List", room_id=room_id)
    add_item(item_name="Apples", list_id=list_id)
    item_id, _ = find_item_by_name(list_id=list_id, item_name="apples")

    update_item_done(item_id=item_id, list_id=list_id, done=True)
    item = find_item_by_name(list_id=list_id, item_name="apples")
    assert item[1] == 1  # done=True

    update_item_done(item_id=item_id, list_id=list_id, done=False)
    item = find_item_by_name(list_id=list_id, item_name="apples")
    assert item[1] == 0  # done=False


def test_restore_item(room_id):
    # Verify that a "done" item can be restored to "not done".
    list_id, _ = create_list(name="My List", room_id=room_id)
    add_item(item_name="Apples", list_id=list_id)
    item_id, _ = find_item_by_name(list_id=list_id, item_name="apples")
    update_item_done(item_id=item_id, list_id=list_id, done=True)

    restore_item(item_id=item_id, list_id=list_id)
    item = find_item_by_name(list_id=list_id, item_name="apples")
    assert item[1] == 0  # done=False


def test_find_duplicate_name(room_id):
    # Verify that duplicate names are correctly identified, excluding the item being checked itself.
    list_id, _ = create_list(name="My List", room_id=room_id)
    add_item(item_name="Apples", list_id=list_id)
    add_item(item_name="Bananas", list_id=list_id)
    apple_id, _ = find_item_by_name(list_id=list_id, item_name="apples")

    # Check if "bananas" is a duplicate for another item (apples)
    duplicate = find_duplicate_name(
        list_id=list_id, item_id=apple_id, new_name="bananas"
    )
    assert duplicate is not None

    # Check if "apples" is a duplicate for itself (should be False because ID matches)
    assert (
        find_duplicate_name(list_id=list_id, item_id=apple_id, new_name="apples")
        is None
    )

    # Check that it's list-specific
    other_list_id, _ = create_list(name="Other List", room_id=room_id)
    add_item(item_name="Bananas", list_id=other_list_id)
    assert (
        find_duplicate_name(list_id=list_id, item_id=apple_id, new_name="bananas")
        is not None
    )


def test_rename_item(room_id):
    # Verify that an item's name can be changed successfully.
    list_id, _ = create_list(name="My List", room_id=room_id)
    add_item(item_name="Apples", list_id=list_id)
    apple_id, _ = find_item_by_name(list_id=list_id, item_name="apples")

    rename_item(item_id=apple_id, list_id=list_id, new_name="granny smith")
    assert find_item_by_name(list_id=list_id, item_name="apples") is None
    assert find_item_by_name(list_id=list_id, item_name="granny smith") is not None


def test_get_lists_sorting(room_id):
    # Verify that lists are returned sorted by name (case-insensitive).
    create_list(name="Zebra", room_id=room_id)
    create_list(name="Apple", room_id=room_id)
    create_list(name="banana", room_id=room_id)
    
    lists = get_lists(room_id)
    names = [entry[1] for entry in lists if entry[1] != "default"]
    assert names == ["apple", "banana", "zebra"]

def test_get_list_data_sorting(room_id):
    # Verify that items are sorted by 'done' status first, then by name (case-insensitive).
    list_id, _ = create_list(name="My List", room_id=room_id)
    add_item(item_name="Zebra", list_id=list_id)
    add_item(item_name="Apple", list_id=list_id)
    add_item(item_name="banana", list_id=list_id)
    
    apple_id, _ = find_item_by_name(list_id=list_id, item_name="apple")
    update_item_done(item_id=apple_id, list_id=list_id, done=True)
    
    items, _ = get_list_data(list_id=list_id)
    # Expected: banana (False), Zebra (False), Apple (True)
    assert items[0]["name"] == "banana"
    assert items[1]["name"] == "Zebra"
    assert items[2]["name"] == "Apple"

def test_get_list_data_history_isolation(room_id):
    # Verify that the history (unique item names) is correctly scoped to the list.
    list1_id, _ = create_list(name="List 1", room_id=room_id)
    list2_id, _ = create_list(name="List 2", room_id=room_id)
    
    add_item(item_name="Apple", list_id=list1_id)
    add_item(item_name="Banana", list_id=list2_id)
    
    _, history1 = get_list_data(list_id=list1_id)
    _, history2 = get_list_data(list_id=list2_id)
    
    assert history1 == ["Apple"]
    assert history2 == ["Banana"]

def test_delete_item(room_id):
    # Verify that an item can be removed from a list.
    list_id, _ = create_list(name="My List", room_id=room_id)
    add_item(item_name="Apples", list_id=list_id)
    apple_id, _ = find_item_by_name(list_id=list_id, item_name="apples")
    
    delete_item(item_id=apple_id, list_id=list_id)
    assert find_item_by_name(list_id=list_id, item_name="apples") is None

def test_delete_nonexistent_item(room_id):
    # Verify that attempting to delete an item that doesn't exist does not raise an error.
    list_id, _ = create_list(name="My List", room_id=room_id)
    # This should simply do nothing and not crash
    delete_item(item_id=999, list_id=list_id)

def test_update_nonexistent_item_done(room_id):
    # Verify that attempting to update a non-existent item does not raise an error.
    list_id, _ = create_list(name="My List", room_id=room_id)
    update_item_done(item_id=999, list_id=list_id, done=True)


def test_rename_list(room_id):
    # Verify that a list can be renamed and it reflects in get_lists.
    list_id, _ = create_list(name="Old Name", room_id=room_id)
    rename_list(list_id=list_id, new_name="new name")
    
    lists = get_lists(room_id)
    assert any(entry[1] == "new name" for entry in lists)
    assert not any(entry[1] == "old name" for entry in lists)


def test_find_list_by_name(room_id):
    # Verify that a list can be found by its name.
    create_list(name="Search Me", room_id=room_id)
    assert find_list_by_name("search me", room_id) is not None
    assert find_list_by_name("nonexistent", room_id) is None


def test_delete_list(room_id):
    # Verify that a list and its items are correctly deleted.
    list_id, _ = create_list(name="Delete Me", room_id=room_id)
    add_item(item_name="Item 1", list_id=list_id)
    
    delete_list(list_id=list_id)
    
    lists = get_lists(room_id)
    assert not any(entry[0] == list_id for entry in lists)
    
    # Verify items are gone too
    items, _ = get_list_data(list_id=list_id)
    assert len(items) == 0


def test_concurrent_db_operations_do_not_share_cursor_state(room_id):
    # Regression test: concurrent CRUD calls should not fail with shared-cursor errors.
    worker_count = 6
    operations_per_worker = 20

    def worker(worker_id: int):
        local_errors = []
        for i in range(operations_per_worker):
            try:
                list_id, _ = create_list(name=f"worker-{worker_id}-list-{i}", room_id=room_id)
                add_item(item_name=f"item-{worker_id}-{i}", list_id=list_id)
                get_list_data(list_id=list_id)
                get_lists(room_id)
            except Exception as exc:  # pragma: no cover - only used for assertion context
                local_errors.append(exc)
        return local_errors

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        results = list(executor.map(worker, range(worker_count)))

    errors = [error for worker_errors in results for error in worker_errors]
    assert errors == []
