from database_crud import (
    add_item,
    delete_item,
    delete_list,
    find_duplicate_name,
    find_item_by_name,
    find_list_by_name,
    get_lists,
    normalize_item_name,
    rename_item,
    rename_list,
    restore_item,
    update_item_done,
)

STATUS_INVALID_NAME = "invalid_name"
STATUS_ADDED = "added"
STATUS_RESTORED = "restored"
STATUS_DUPLICATE_ACTIVE = "duplicate_active"
STATUS_DUPLICATE_NAME = "duplicate_name"
STATUS_RENAMED = "renamed"
STATUS_UPDATED = "updated"
STATUS_DELETED = "deleted"


def add_or_restore_item(list_id: int, raw_name: str | None) -> tuple[str, str | None]:
    item_name = normalize_item_name(raw_name)
    if not item_name:
        return STATUS_INVALID_NAME, None

    existing = find_item_by_name(list_id=list_id, item_name=item_name)
    if existing:
        item_id, is_done = existing
        if is_done:
            restore_item(item_id=item_id, list_id=list_id)
            return STATUS_RESTORED, item_name
        return STATUS_DUPLICATE_ACTIVE, item_name

    add_item(item_name=item_name, list_id=list_id)
    return STATUS_ADDED, item_name


def rename_item_with_checks(
    list_id: int, item_id: int, raw_name: str | None
) -> tuple[str, str | None]:
    new_name = normalize_item_name(raw_name)
    if not new_name:
        return STATUS_INVALID_NAME, None

    duplicate = find_duplicate_name(list_id=list_id, item_id=item_id, new_name=new_name)
    if duplicate:
        return STATUS_DUPLICATE_NAME, new_name

    rename_item(item_id=item_id, list_id=list_id, new_name=new_name)
    return STATUS_RENAMED, new_name


def rename_list_with_checks(list_id: int, raw_name: str | None) -> tuple[str, str | None]:
    new_name = normalize_item_name(raw_name)
    if not new_name:
        return STATUS_INVALID_NAME, None

    duplicate = find_list_by_name(new_name)
    if duplicate and duplicate[0] != list_id:
        return STATUS_DUPLICATE_NAME, new_name

    rename_list(list_id=list_id, new_name=new_name)
    return STATUS_RENAMED, new_name


def toggle_item_done(list_id: int, item_id: int, done: bool) -> str:
    update_item_done(item_id=item_id, list_id=list_id, done=done)
    return STATUS_UPDATED


def delete_item_from_list(list_id: int, item_id: int) -> str:
    delete_item(item_id=item_id, list_id=list_id)
    return STATUS_DELETED


def delete_list_and_items(list_id: int) -> tuple[str, int]:
    delete_list(list_id)
    # Return next list_id to switch to (if any)
    remaining_lists = get_lists()
    if not remaining_lists:
        # Re-initialize to get a new default_list_id
        from database_setup import init_database
        _, _, default_list_id = init_database()
        return STATUS_DELETED, default_list_id
    
    return STATUS_DELETED, remaining_lists[0][0]
