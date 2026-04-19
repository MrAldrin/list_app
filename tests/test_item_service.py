import pytest
from unittest.mock import patch

from item_service import (
    STATUS_ADDED,
    STATUS_DELETED,
    STATUS_DUPLICATE_ACTIVE,
    STATUS_DUPLICATE_NAME,
    STATUS_INVALID_NAME,
    STATUS_RENAMED,
    STATUS_RESTORED,
    STATUS_UPDATED,
    add_or_restore_item,
    delete_item_from_list,
    rename_item_with_checks,
    toggle_item_done,
)


@patch("item_service.find_item_by_name")
@patch("item_service.restore_item")
@patch("item_service.add_item")
@pytest.mark.parametrize("raw_name", ["", "   ", "\n", "\t", None])
def test_add_or_restore_item_invalid_name(mock_add, mock_restore, mock_find, raw_name):
    # Test that adding an empty, whitespace-only, or None name is rejected
    status, name = add_or_restore_item(list_id=1, raw_name=raw_name)
    assert status == STATUS_INVALID_NAME
    assert name is None
    mock_find.assert_not_called()
    mock_add.assert_not_called()
    mock_restore.assert_not_called()


@patch("item_service.find_item_by_name")
@patch("item_service.restore_item")
@patch("item_service.add_item")
@pytest.mark.parametrize("raw_name, expected_name", [
    ("Apples", "apples"),
    ("  banaNAs  ", "bananas"),
    ("Bread and milk", "bread and milk"),
])
def test_add_or_restore_item_new(mock_add, mock_restore, mock_find, raw_name, expected_name):
    # Test that a completely new item is successfully added and normalized
    mock_find.return_value = None
    status, name = add_or_restore_item(list_id=1, raw_name=raw_name)
    assert status == STATUS_ADDED
    assert name == expected_name
    mock_add.assert_called_once_with(item_name=expected_name, list_id=1)
    mock_restore.assert_not_called()


@patch("item_service.find_item_by_name")
@patch("item_service.restore_item")
@patch("item_service.add_item")
def test_add_or_restore_item_restore(mock_add, mock_restore, mock_find):
    # Test that adding an item that was previously marked as "done" will restore it
    mock_find.return_value = (10, True)  # id=10, is_done=True
    status, name = add_or_restore_item(list_id=1, raw_name="apples")
    assert status == STATUS_RESTORED
    assert name == "apples"
    mock_restore.assert_called_once_with(item_id=10, list_id=1)
    mock_add.assert_not_called()


@patch("item_service.find_item_by_name")
@patch("item_service.restore_item")
@patch("item_service.add_item")
def test_add_or_restore_item_duplicate_active(mock_add, mock_restore, mock_find):
    # Test that adding an item that is already active (not done) is blocked as a duplicate
    mock_find.return_value = (10, False)  # id=10, is_done=False
    status, name = add_or_restore_item(list_id=1, raw_name="Apples")
    assert status == STATUS_DUPLICATE_ACTIVE
    assert name == "apples"
    mock_restore.assert_not_called()
    mock_add.assert_not_called()


@patch("item_service.find_duplicate_name")
@patch("item_service.rename_item")
@pytest.mark.parametrize("raw_name", ["", "   ", "\n", "\t", None])
def test_rename_item_with_checks_invalid_name(mock_rename, mock_find_duplicate, raw_name):
    # Test that renaming an item to an empty, whitespace-only string, or None is rejected
    status, name = rename_item_with_checks(list_id=1, item_id=10, raw_name=raw_name)
    assert status == STATUS_INVALID_NAME
    assert name is None
    mock_find_duplicate.assert_not_called()
    mock_rename.assert_not_called()


@patch("item_service.find_duplicate_name")
@patch("item_service.rename_item")
def test_rename_item_with_checks_duplicate(mock_rename, mock_find_duplicate):
    # Test that renaming an item to a name that already exists is blocked
    mock_find_duplicate.return_value = (11,)  # Found another item with this name
    status, name = rename_item_with_checks(list_id=1, item_id=10, raw_name="bananas")
    assert status == STATUS_DUPLICATE_NAME
    assert name == "bananas"
    mock_rename.assert_not_called()


@patch("item_service.find_duplicate_name")
@patch("item_service.rename_item")
@pytest.mark.parametrize("raw_name, expected_name", [
    ("Bananas", "bananas"),
    ("  Milk  ", "milk"),
    ("Apples", "apples"), # If the current name is 'apples', this is renaming to self
])
def test_rename_item_with_checks_success(mock_rename, mock_find_duplicate, raw_name, expected_name):
    # Test that renaming an item to a valid, unique name succeeds
    mock_find_duplicate.return_value = None
    status, name = rename_item_with_checks(list_id=1, item_id=10, raw_name=raw_name)
    assert status == STATUS_RENAMED
    assert name == expected_name
    mock_rename.assert_called_once_with(item_id=10, list_id=1, new_name=expected_name)


@patch("item_service.update_item_done")
@pytest.mark.parametrize("done", [True, False])
def test_toggle_item_done(mock_update, done):
    # Test that an item's done status can be successfully toggled to True or False
    status = toggle_item_done(list_id=1, item_id=10, done=done)
    assert status == STATUS_UPDATED
    mock_update.assert_called_once_with(item_id=10, list_id=1, done=done)


@patch("item_service.delete_item")
def test_delete_item_from_list(mock_delete):
    # Test that an item can be successfully deleted from a list
    status = delete_item_from_list(list_id=1, item_id=10)
    assert status == STATUS_DELETED
    mock_delete.assert_called_once_with(item_id=10, list_id=1)
