# Item writes and stale pages

Several people can have the same list open. A page can be "stale": it shows an
older state than the database. These rules stop a stale page from overwriting
newer changes or writing half an update.

## Core rules

- **Check identity inside the write.** Every list write passes the list's
  identity and the database checks it in the same transaction as the change.
  Room pages send the list slug (`expected_slug`); public pages send
  `share:<token>`. SQLite can reuse a deleted list's numeric ID, so the ID alone
  is not enough. Tests: `tests/test_list_identity.py`.
- **Send intent, not a whole value.** Buttons send "add 1" or "toggle tag X",
  not the full value the page last saw. The database applies it to the current
  data.
- **One transaction per user action.** Multi-field changes either all succeed
  or all roll back. Failed writes leave no open transaction.

All helpers live in `src/database_crud.py`.

## Per action

| Action | Behavior | Tests |
|---|---|---|
| Quantity +/− | Adds the delta in SQL (`adjust_item_quantity`); never below 1; empty counts as 1. The edit dialog sets an absolute value. | `tests/test_quantity_updates.py` |
| Add | Add, restore a checked item, or reject a duplicate in one transaction (`add_or_restore_item_atomic`). A unique index blocks duplicate names per list, ignoring case and outer spaces. | `tests/test_item_uniqueness.py` |
| Edit dialog | Name, description and quantity saved together (`update_item_details`). A blank or duplicate name changes nothing. | `tests/test_item_edits.py` |
| Rename item | Duplicate check and rename in one transaction (`rename_item_with_checks`); list identity checked first. | `tests/test_item_renames.py` |
| Item tag button | Toggles one tag on the current stored tags (`toggle_item_active_tag`). | `tests/test_database_crud.py` |
| List tags | Add/remove one tag (`add_list_tag`, `remove_list_tag`); tag undo reuses add. | `tests/test_database_crud.py`, `tests/test_list_tag_ui.py` |
| Rename list | Identity, room ownership and name uniqueness checked in the same transaction. A lost race returns the normal duplicate-name warning. | `tests/test_list_renames.py` |
| Delete + undo | Undo restores name, done state, tags, description and quantity as a new item. If the name was re-added meanwhile, undo warns and changes nothing. | `tests/test_item_undo.py` |
| Delete list / room | All deletes roll back if any step fails. | `tests/test_database_crud.py` |
| Admin password reset | The dialog remembers room ID and slug; if the room was deleted or replaced, nothing changes and the UI says so. | `tests/test_admin_rooms.py`, `tests/test_database_crud.py` |

If the app starts with duplicate item names already in the database, it stops
with a clear migration error instead of deleting any. Fix the duplicates and
restart.

## Item identity

Item IDs are never reused: the `items` table uses `AUTOINCREMENT` (migration 2).
A stale checkbox, quantity, tag, edit or delete action on a deleted item
matches no row and changes nothing. Tests: `tests/test_item_ids.py`.

Finer details and test scope are in
[background](background/item-writes.md).
