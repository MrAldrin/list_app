# Item writes and stale pages

## Quantity buttons

The +/− buttons apply a delta directly to the stored quantity in SQL rather than
save a value calculated from an older UI view. `adjust_item_quantity` in
`src/database_crud.py` keeps the minimum at one and treats legacy null quantities
as one before applying the delta. Updates are scoped to the item and list.
Explicit quantity edits in the edit dialog still set an absolute value.

## Add field

Adding an item, restoring a completed item, or rejecting an active duplicate now
happens inside one write transaction (`add_or_restore_item_atomic`). This
serializes add/restore calls in the supported single-instance app, even when
browsers submit at the same time. A database-level unique-name index is deferred
until existing production data can be checked; direct SQL writes are not covered
by this guarantee. Concurrent app requests are tested in
`tests/test_item_uniqueness.py`.

## Edit dialog

Saving the edit dialog writes name, description, and quantity in one
transaction (`update_item_details` in `src/database_crud.py`). The duplicate-name
check runs inside that transaction, so an empty or duplicate name leaves every
field unchanged. Regression tests are in `tests/test_item_edits.py`.

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

These protections do not make every multi-step edit atomic. Manual multi-user
verification remains in the [backlog](../plans/backlog.md).
