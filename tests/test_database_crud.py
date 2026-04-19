import pytest
from database_crud import (
    normalize_item_name,
    get_lists,
    create_list,
    get_list_data,
    find_item_by_name,
    restore_item,
    add_item,
    update_item_done,
    find_duplicate_name,
    rename_item,
    delete_item,
)


def test_normalize_item_name():
    # Verify that raw item names are correctly stripped, lowercased, and handle None.
    assert normalize_item_name(raw="  Apples  ") == "apples"
    assert normalize_item_name(raw=None) == ""
    assert normalize_item_name(raw="\nBREAD\t") == "bread"


def test_create_list_success():
    # Verify that a new list can be created and is included in the list of all lists.
    list_id = create_list(name="Groceries")
    assert list_id is not None
    lists = get_lists()
    # Expect 2 lists: "default" (from conftest.py) and "groceries"
    assert len(lists) == 2
    assert any(l[1] == "groceries" for l in lists)
    assert any(l[1] == "default" for l in lists)


def test_create_list_duplicate():
    # Verify that creating a list with a name that already exists returns the existing ID.
    create_list(name="Groceries")
    # This should return the same ID and not create a new row
    list_id2 = create_list(name="GROCERIES")
    lists = get_lists()
    assert len([l for l in lists if l[1] == "groceries"]) == 1


def test_create_list_empty():
    # Verify that creating a list with an empty or whitespace-only name raises a ValueError.
    with pytest.raises(
        expected_exception=ValueError, match="List name cannot be empty"
    ):
        create_list(name="")
    with pytest.raises(
        expected_exception=ValueError, match="List name cannot be empty"
    ):
        create_list(name="   ")


def test_add_and_get_items():
    # Verify that items can be added to a list and retrieved with correct sorting and history.
    list_id = create_list(name="My List")
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


def test_find_item_by_name():
    # Verify that an item can be found by its name within a specific list.
    list_id = create_list(name="My List")
    add_item(item_name="Apples", list_id=list_id)

    item = find_item_by_name(list_id=list_id, item_name="apples")
    assert item is not None
    assert item[1] == 0  # done=False

    assert find_item_by_name(list_id=list_id, item_name="nonexistent") is None
    # Check that it's list-specific
    other_list_id = create_list(name="Other List")
    assert find_item_by_name(list_id=other_list_id, item_name="apples") is None


def test_update_item_done():
    # Verify that an item's completion status can be updated.
    list_id = create_list(name="My List")
    add_item(item_name="Apples", list_id=list_id)
    item_id, _ = find_item_by_name(list_id=list_id, item_name="apples")

    update_item_done(item_id=item_id, list_id=list_id, done=True)
    item = find_item_by_name(list_id=list_id, item_name="apples")
    assert item[1] == 1  # done=True

    update_item_done(item_id=item_id, list_id=list_id, done=False)
    item = find_item_by_name(list_id=list_id, item_name="apples")
    assert item[1] == 0  # done=False


def test_restore_item():
    # Verify that a "done" item can be restored to "not done".
    list_id = create_list(name="My List")
    add_item(item_name="Apples", list_id=list_id)
    item_id, _ = find_item_by_name(list_id=list_id, item_name="apples")
    update_item_done(item_id=item_id, list_id=list_id, done=True)

    restore_item(item_id=item_id, list_id=list_id)
    item = find_item_by_name(list_id=list_id, item_name="apples")
    assert item[1] == 0  # done=False


def test_find_duplicate_name():
    # Verify that duplicate names are correctly identified, excluding the item being checked itself.
    list_id = create_list(name="My List")
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
    other_list_id = create_list(name="Other List")
    add_item(item_name="Bananas", list_id=other_list_id)
    assert (
        find_duplicate_name(list_id=list_id, item_id=apple_id, new_name="bananas")
        is not None
    )


def test_rename_item():
    # Verify that an item's name can be changed successfully.
    list_id = create_list(name="My List")
    add_item(item_name="Apples", list_id=list_id)
    apple_id, _ = find_item_by_name(list_id=list_id, item_name="apples")

    rename_item(item_id=apple_id, list_id=list_id, new_name="granny smith")
    assert find_item_by_name(list_id=list_id, item_name="apples") is None
    assert find_item_by_name(list_id=list_id, item_name="granny smith") is not None


def test_delete_item():
    # Verify that an item can be removed from a list.
    list_id = create_list(name="My List")
    add_item(item_name="Apples", list_id=list_id)
    apple_id, _ = find_item_by_name(list_id=list_id, item_name="apples")

    delete_item(item_id=apple_id, list_id=list_id)
    assert find_item_by_name(list_id=list_id, item_name="apples") is None
