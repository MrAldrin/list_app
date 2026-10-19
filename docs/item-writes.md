# Item writes and stale pages

Several people can have the same list open. A page can be "stale": it shows an
older state than the database. These rules stop a stale page from overwriting
newer changes or writing half an update.

## Core rules

- **Check identity inside the write.** Room writes find lists and items by
  their public `uid`, which is never reused. Share links are checked in the same
  transaction as the change. A stale page gets an error and nothing changes.
- **Send intent, not a whole value.** Buttons send "add 1" or "toggle tag X",
  not the full value the page last saw. The database applies it to the current
  data.
- **One transaction per user action.** Multi-field changes either all succeed
  or all roll back. Failed writes leave no open transaction.
- **Late edits are checked.** A rename, edit or tick carries the `changed_seq`
  the page saw. If someone else changed the same value since, the write is
  refused (`changed_meanwhile`). See [conflicts](api.md#conflicts).

All helpers live in `src/database_crud.py`. The [JSON API](api.md) calls
their `_locked` variants inside one write transaction, so each rule has one copy.

## Per action

| Action | Behavior | Tests |
|---|---|---|
| Quantity +/− | Adds the delta in SQL (`adjust_item_quantity_locked`); never below 1; empty counts as 1. The edit dialog sets an absolute value. | `tests/test_quantity_updates.py` |
| Add | Add, restore a checked item, or reject a duplicate in one transaction (`add_or_restore_item_locked`). A unique index blocks duplicate names per list, ignoring case and outer spaces. Adding and restoring count (`add_count`, `added_at`). | `tests/test_item_uniqueness.py`, `tests/test_times_added.py` |
| Edit dialog | Name, description, quantity and date saved together (`update_item_details_locked`). The date is optional and can be cleared. Renaming to a duplicate name changes nothing. A stale edit of a changed value changes nothing (`changed_meanwhile`). | `tests/test_item_edits.py`, `tests/test_item_date.py`, `tests/test_item_renames.py`, `tests/test_api_conflicts.py` |
| Item tag button | Toggles one tag on the current stored tags (`toggle_item_active_tag_locked`). An `active` value sets the state instead and is safe to repeat. | `tests/test_api_tag_ops.py`, `tests/test_tags.py`, `tests/test_api_conflicts.py` |
| List tags | Add/remove one tag (`change_list_tag_locked`); tag undo reuses add. | `tests/test_api_tag_ops.py`, `tests/test_tags.py` |
| Rename list | Identity, room ownership and name uniqueness checked in the same transaction. A lost race returns the normal duplicate-name warning. A stale rename of a changed name changes nothing (`changed_meanwhile`). | `tests/test_list_renames.py`, `tests/test_api_conflicts.py` |
| Check / uncheck | A toast names the item ("Checked milk", "Unchecked milk") with Undo for 5 s, so a tap on the wrong item while the list moves is easy to spot. Undo sets the item back, unless it is gone or someone already changed it back. Unchecking counts as an add; checking does not ([JSON API](api.md#operation-types)). | `browser_tests/test_svelte_items.py`, `browser_tests/test_svelte_times_added.py`, `tests/test_times_added.py` |
| Delete + undo | Undo restores name, done state, tags, description, quantity, date and add count as a new item. If the name was re-added meanwhile, undo warns and changes nothing. | `tests/test_item_undo.py`, `tests/test_item_date.py`, `tests/test_times_added.py` |
| Delete list / room | All deletes roll back if any step fails. | `tests/test_database_crud.py` |
| Admin password reset | The API finds the room by slug in the write transaction. If the room was deleted or replaced, nothing changes and the UI says so. | `tests/test_database_crud.py`, `tests/test_api_admin.py` |

## Field rules

Text is trimmed first. Item names are lowercase. Text and count limits, with
their error codes, are in [rejection codes](api.md#rejection-codes). The Svelte
inputs use the same text limits (`maxlength`).

Unchecking an item, or adding a tag the list already has, still works when the
list is full.

The database guards the same rules as a safety net (migration 6): `BEFORE
INSERT` and `BEFORE UPDATE` triggers reject blank or untrimmed names, missing
slugs, quantities below 1, `done` other than 0 or 1, a completion time on an
unchecked item, and tags that are not a JSON array. A rejected write raises
`sqlite3.IntegrityError`. Rules and reasons: the
[field constraints background](background/field-constraints.md). Tests:
`tests/test_field_limits.py`, `tests/test_field_rules_migration.py`.

## Item identity

Item IDs are never reused: the `items` table uses `AUTOINCREMENT` (migration 2).
A stale checkbox, quantity, tag, edit or delete action on a deleted item
matches no row and changes nothing. Tests: `tests/test_item_ids.py`.

Finer details and test scope are in
[background](background/item-writes.md).
