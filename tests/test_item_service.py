from unittest.mock import patch

import pytest

from database_crud import ListUnavailable
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
    update_item_details_with_checks,
)


@patch("item_service.add_or_restore_item_atomic")
@pytest.mark.parametrize("raw_name", ["", "   ", "\n", "\t", None])
def test_add_or_restore_item_invalid_name(mock_write, raw_name):
    status, name = add_or_restore_item(list_id=1, raw_name=raw_name)
    assert (status, name) == (STATUS_INVALID_NAME, None)
    mock_write.assert_not_called()


@patch("item_service.add_or_restore_item_atomic")
@pytest.mark.parametrize(
    "raw_name, expected_name",
    [
        ("Apples", "apples"),
        ("  banaNAs  ", "bananas"),
        ("Bread and milk", "bread and milk"),
    ],
)
def test_add_or_restore_item_new(mock_write, raw_name, expected_name):
    mock_write.return_value = STATUS_ADDED
    assert add_or_restore_item(1, raw_name) == (STATUS_ADDED, expected_name)
    mock_write.assert_called_once_with(
        item_name=expected_name, list_id=1, expected_slug=None
    )


@patch("item_service.add_or_restore_item_atomic")
@pytest.mark.parametrize("result", [STATUS_RESTORED, STATUS_DUPLICATE_ACTIVE])
def test_add_or_restore_item_existing(mock_write, result):
    mock_write.return_value = result
    assert add_or_restore_item(1, " Apples ") == (result, "apples")
    mock_write.assert_called_once_with(
        item_name="apples", list_id=1, expected_slug=None
    )


@patch("item_service.find_duplicate_name")
@patch("item_service.rename_item")
@pytest.mark.parametrize("raw_name", ["", "   ", "\n", "\t", None])
def test_rename_item_with_checks_invalid_name(
    mock_rename, mock_find_duplicate, raw_name
):
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
@pytest.mark.parametrize(
    "raw_name, expected_name",
    [
        ("Bananas", "bananas"),
        ("  Milk  ", "milk"),
        (
            "Apples",
            "apples",
        ),  # If the current name is 'apples', this is renaming to self
    ],
)
def test_rename_item_with_checks_success(
    mock_rename, mock_find_duplicate, raw_name, expected_name
):
    # Test that renaming an item to a valid, unique name succeeds
    mock_find_duplicate.return_value = None
    status, name = rename_item_with_checks(list_id=1, item_id=10, raw_name=raw_name)
    assert status == STATUS_RENAMED
    assert name == expected_name
    mock_rename.assert_called_once_with(
        item_id=10, list_id=1, new_name=expected_name, expected_slug=None
    )


@patch("item_service.update_item_done")
@pytest.mark.parametrize("done", [True, False])
def test_toggle_item_done(mock_update, done):
    # Test that an item's done status can be successfully toggled to True or False
    status = toggle_item_done(list_id=1, item_id=10, done=done)
    assert status == STATUS_UPDATED
    mock_update.assert_called_once_with(
        item_id=10, list_id=1, done=done, expected_slug=None
    )


@patch("item_service.delete_item")
def test_delete_item_from_list(mock_delete):
    # Test that an item can be successfully deleted from a list
    status = delete_item_from_list(list_id=1, item_id=10)
    assert status == STATUS_DELETED
    mock_delete.assert_called_once_with(item_id=10, list_id=1, expected_slug=None)


@patch("item_service.update_item_details")
def test_update_item_details_with_checks_success(mock_update):
    # Test updating item name, description, and quantity with checks
    mock_update.return_value = True
    status, name = update_item_details_with_checks(
        list_id=1,
        item_id=10,
        raw_name="  Apples  ",
        raw_description="  Organic 5-pack  ",
        quantity=0,
    )
    assert status == STATUS_RENAMED
    assert name == "apples"
    mock_update.assert_called_once_with(
        item_id=10,
        list_id=1,
        name="apples",
        description="Organic 5-pack",
        quantity=1,
        expected_slug=None,
    )


@patch("item_service.update_item_details")
def test_update_item_details_with_checks_duplicate(mock_update):
    mock_update.return_value = False
    status, name = update_item_details_with_checks(
        list_id=1, item_id=10, raw_name="Pears", raw_description="", quantity=2
    )
    assert status == STATUS_DUPLICATE_NAME
    assert name == "pears"


@patch("item_service.update_item_quantity")
def test_set_item_quantity(mock_update_qty):
    from item_service import set_item_quantity

    status = set_item_quantity(list_id=1, item_id=10, quantity=3)
    assert status == STATUS_UPDATED
    mock_update_qty.assert_called_once_with(
        item_id=10, list_id=1, quantity=3, expected_slug=None
    )

    # Test clamping minimum quantity to 1
    mock_update_qty.reset_mock()
    set_item_quantity(list_id=1, item_id=10, quantity=0)
    mock_update_qty.assert_called_once_with(
        item_id=10, list_id=1, quantity=1, expected_slug=None
    )


def test_add_or_restore_propagates_deleted_list_error(monkeypatch):
    monkeypatch.setattr(
        "item_service.add_or_restore_item_atomic",
        lambda **_kwargs: (_ for _ in ()).throw(ListUnavailable()),
    )

    with pytest.raises(ListUnavailable):
        add_or_restore_item(list_id=1, raw_name="apples")
