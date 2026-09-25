# Item writes and stale pages

## Quantity buttons

The +/− buttons apply a delta directly to the stored quantity in SQL rather than
save a value calculated from an older UI view. `adjust_item_quantity` in
`src/database_crud.py` keeps the minimum at one and treats legacy null quantities
as one before applying the delta. Updates are scoped to the item and list.
Explicit quantity edits in the edit dialog still set an absolute value.

## Add field

Adding an item, restoring a completed item, or rejecting an active duplicate now
happens inside one write transaction (`add_or_restore_item_atomic`). A unique
SQLite index also prevents duplicate names per list, ignoring case and surrounding
spaces. On startup, existing duplicates cause a clear migration error rather
than being discarded; resolve them before restarting. Concurrent requests are
covered in `tests/test_item_uniqueness.py`.

## Edit dialog

Saving the edit dialog writes name, description, and quantity in one
transaction (`update_item_details` in `src/database_crud.py`). The duplicate-name
check runs inside that transaction, so an empty or duplicate name leaves every
field unchanged. Regression tests are in `tests/test_item_edits.py`.

The service-level name-only rename (`rename_item_with_checks`) also checks for a
duplicate and updates the name in one write transaction. If another write claims
the requested name first, the service returns the duplicate-name status instead
of risking a duplicate write or SQLite error. It validates `expected_slug` before
checking duplicates, so an old page cannot make a decision about a replacement
list that reused its ID. Name-only renames leave description and quantity intact;
see `tests/test_item_renames.py`.

## Quick item-tag toggles

Quick tag buttons submit the tag being toggled, not the whole `active_tags`
array rendered by that browser. `toggle_item_active_tag` reads the persisted array
and applies the toggle under `_DB_LOCK` and `BEGIN IMMEDIATE`, after validating
the page's private slug or public share-token identity. Thus two stale pages can
toggle different tags without replacing one another's updates. The existing
full-array `update_item_active_tags` setter remains available for replacement
semantics, but the quick-tag UI no longer uses it. Item-deletion undo still
restores the captured tags on the newly created item.

List-tag add and delete callbacks submit a single tag intent through
`add_list_tag` or `remove_list_tag`. Each helper reads and updates the current
persisted tag array under `_DB_LOCK` and `BEGIN IMMEDIATE`, after validating the
page's private slug or public share token. Tag undo uses the same atomic add
operation. Stale pages therefore cannot replace unrelated tag changes; the
full-array `update_list_tags_settings` setter remains available for callers that
intentionally need replacement semantics. Tests cover concurrent distinct adds,
a delete interleaved with an add, undo interleaving, UI feedback, stale-list
rejection, and injected SQL failure recovery.

## List rename

The private room's admin rename checks the list's `expected_slug`, room ownership,
and room-scoped name uniqueness in the same write transaction as the update.
If another create or rename claims the name first, the service returns its normal
duplicate-name status, so the UI can show its existing warning without leaving
the rename transaction open. The token-authorized rename remains a separate path
that validates its room token and list ownership in its write transaction.
Regression coverage is in `tests/test_list_renames.py`.

## Delete and undo

Undo restores the deleted item's name, done state, tags, description, and quantity
in one transaction. It creates a new item ID (the original ID is not reserved).
If someone adds the same name first, undo shows a warning and does not overwrite
that item. The list identity is checked within the same transaction.

## List identity

SQLite can reuse a deleted list's numeric ID. Room-page writes pass the original
list slug as `expected_slug`; public-page writes pass `share:<token>` instead
(see [public sharing](public-sharing.md)). Database helpers check that identity
within the same write transaction before mutating data. An old page must not edit a new
list that happens to reuse its ID. The optional argument exists for other callers;
a numeric ID alone is not the stale-page safeguard.

## Item identity still needs a separate safeguard

The list slug or share token protects *list* identity, not an individual item's
identity. SQLite may reuse a deleted maximum item ID within the same live list.
A stale quick-tag callback can then change the replacement item despite passing
valid list identity; checkbox, quantity, edit-save, and delete callbacks also
retain numeric item IDs. This confirmed risk remains deferred pending an
[item-identity decision](../plans/backlog.md#data-correctness--next-priorities).
The atomic tag and edit checks above do not resolve it.

## Admin room password reset

The admin reset dialog retains the room ID and slug from when it was opened.
`update_room_password` checks both inside its `BEGIN IMMEDIATE` transaction before
changing the password or deleting room-access tokens. If the room was deleted or
its numeric ID now belongs to a different room, the helper returns `False`; the
UI closes the stale dialog, reports that the target changed, and refreshes the
room list instead of claiming success. Password hashing remains outside the
transaction. Existing ID-only helper calls remain supported for non-UI callers.
The stale-target and injected token-deletion failure cases are covered in
`tests/test_database_crud.py` and `tests/test_admin_rooms.py`.

## Deletion rollback

List deletion (including room-token authorization) and room deletion (including
password verification) run inside write transactions. If a later delete fails,
earlier item/list deletes roll back instead of leaving a partial deletion.
Injected-failure regression tests exercise these paths.

The ID-based `create_list`, `create_room`, and `rename_room` helpers, plus
`revoke_room_access_token`, also roll back and re-raise when their SQL write or
commit fails. In particular, a failed token revocation leaves the token active.
Injected `RAISE(ABORT)` tests verify unchanged rows, a closed transaction, and a
subsequent successful write in `tests/test_database_crud.py`. This only covers
failure cleanup for these entry points; it does not make every multi-step edit
atomic.

## Cross-path regression scope

`tests/test_write_atomicity_cross_path.py` exercises room-token list creation,
private and public list writes, rejected room authorization and duplicate names,
then successful writes. It checks that rejections leave persisted data unchanged
and no open transaction, while successful writes preserve room access, the list
slug and share token, list/item tags, item descriptions and quantities.
Existing service tests check duplicate-edit status; UI tests check tag-action
feedback and stale admin room password-reset dialogs. The cross-path test does
not simulate browser callbacks. These automated checks do not prove every write
path, real-device behavior, or production concurrency. Remaining item-identity
and manual checks are in the [backlog](../plans/backlog.md).
