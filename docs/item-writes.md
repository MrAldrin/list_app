# Item writes and stale pages

## Quantity buttons

The +/− buttons apply a delta directly to the stored quantity in SQL rather than
save a value calculated from an older UI view. `adjust_item_quantity` in
`src/database_crud.py` keeps the minimum at one and treats legacy null quantities
as one before applying the delta. Updates are scoped to the item and list.
Explicit quantity edits in the edit dialog still set an absolute value.

## List identity

SQLite can reuse a deleted list's numeric ID. Room-page writes pass the original
list slug as `expected_slug`; public-page writes pass `share:<token>` instead
(see [public sharing](public-sharing.md)). Database helpers check that identity
within the same write transaction before mutating data. An old page must not edit a new
list that happens to reuse its ID. The optional argument exists for other callers;
a numeric ID alone is not the stale-page safeguard.

These protections do not make every multi-step edit atomic. Concurrent duplicate
prevention, all-or-nothing name/quantity edits, complete deletion undo, and manual
multi-user verification remain in the [backlog](../plans/backlog.md).
