from database_crud import (
    add_or_restore_item_atomic,
    adjust_item_quantity,
    delete_item,
    delete_list,
    find_list_by_name,
    get_lists,
    normalize_item_name,
    rename_item_if_unique,
    rename_list,
    update_item_details,
    update_item_done,
    update_item_quantity,
)

STATUS_INVALID_NAME = "invalid_name"
STATUS_ADDED = "added"
STATUS_RESTORED = "restored"
STATUS_DUPLICATE_ACTIVE = "duplicate_active"
STATUS_DUPLICATE_NAME = "duplicate_name"
STATUS_RENAMED = "renamed"
STATUS_UPDATED = "updated"
STATUS_DELETED = "deleted"


def add_or_restore_item(
    list_id: int, raw_name: str | None, *, expected_slug: str | None = None
) -> tuple[str, str | None]:
    item_name = normalize_item_name(raw_name)
    if not item_name:
        return STATUS_INVALID_NAME, None

    status = add_or_restore_item_atomic(
        item_name=item_name, list_id=list_id, expected_slug=expected_slug
    )
    return status, item_name


def rename_item_with_checks(
    list_id: int,
    item_id: int,
    raw_name: str | None,
    *,
    expected_slug: str | None = None,
) -> tuple[str, str | None]:
    new_name = normalize_item_name(raw_name)
    if not new_name:
        return STATUS_INVALID_NAME, None

    renamed = rename_item_if_unique(
        item_id=item_id, list_id=list_id, new_name=new_name, expected_slug=expected_slug
    )
    if not renamed:
        return STATUS_DUPLICATE_NAME, new_name
    return STATUS_RENAMED, new_name


def update_item_details_with_checks(
    list_id: int,
    item_id: int,
    raw_name: str | None,
    raw_description: str | None,
    quantity: int | None = None,
    *,
    expected_slug: str | None = None,
) -> tuple[str, str | None]:
    """Validate an item edit, then save every field together or none of them."""
    new_name = normalize_item_name(raw_name)
    if not new_name:
        return STATUS_INVALID_NAME, None

    saved = update_item_details(
        item_id=item_id,
        list_id=list_id,
        name=new_name,
        description=(raw_description or "").strip(),
        quantity=None if quantity is None else max(1, int(quantity)),
        expected_slug=expected_slug,
    )
    if not saved:
        return STATUS_DUPLICATE_NAME, new_name
    return STATUS_RENAMED, new_name


def rename_list_with_checks(
    list_id: int,
    room_id: int,
    raw_name: str | None,
    *,
    expected_slug: str | None = None,
) -> tuple[str, str | None]:
    new_name = normalize_item_name(raw_name)
    if not new_name:
        return STATUS_INVALID_NAME, None

    duplicate = find_list_by_name(new_name, room_id)
    if duplicate and duplicate[0] != list_id:
        return STATUS_DUPLICATE_NAME, new_name

    rename_list(list_id=list_id, new_name=new_name, expected_slug=expected_slug)
    return STATUS_RENAMED, new_name


def toggle_item_done(
    list_id: int, item_id: int, done: bool, *, expected_slug: str | None = None
) -> str:
    update_item_done(
        item_id=item_id, list_id=list_id, done=done, expected_slug=expected_slug
    )
    return STATUS_UPDATED


def set_item_quantity(
    list_id: int, item_id: int, quantity: int, *, expected_slug: str | None = None
) -> str:
    qty = max(1, int(quantity))
    update_item_quantity(
        item_id=item_id, list_id=list_id, quantity=qty, expected_slug=expected_slug
    )
    return STATUS_UPDATED


def change_item_quantity(
    list_id: int, item_id: int, delta: int, *, expected_slug: str | None = None
) -> str:
    adjust_item_quantity(
        item_id=item_id, list_id=list_id, delta=delta, expected_slug=expected_slug
    )
    return STATUS_UPDATED


def delete_item_from_list(
    list_id: int, item_id: int, *, expected_slug: str | None = None
) -> str:
    delete_item(item_id=item_id, list_id=list_id, expected_slug=expected_slug)
    return STATUS_DELETED


def delete_list_and_items(
    list_id: int, room_id: int, *, expected_slug: str | None = None
) -> tuple[str, int | None]:
    delete_list(list_id, expected_slug=expected_slug)
    remaining_lists = get_lists(room_id)
    if not remaining_lists:
        return STATUS_DELETED, None

    return STATUS_DELETED, remaining_lists[0][0]
