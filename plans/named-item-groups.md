# Named item groups

Lifecycle: temporary

## Outcome

Implement named item groups as authorized in the
[feature decision](../plans/decisions-for-heming.md#5-feature-priorities).
The first version stores reusable item names only; no quantities, notes or tags.
A group add skips every existing match, whether active or checked.

**State:** Planned only. No implementation or feature verification has been done.

## Plan

- Proposed scope: groups belong to a room and can be reused on its lists by
  room-authorized people. They are not available through a public share link,
  which grants access to one list rather than room management. Store each
  group's name and ordered item names, validate names and reject duplicate
  names within a group. Keep limits explicit and consistent with the existing
  100-character name and 1,000-item list limits.
- Put group data in the authenticated room feed and saved snapshot so the
  catalog is available offline and live updates reach other room pages. Keep
  create/edit/delete online-only for the first version; do not add group-edit
  operations to the offline queue without defined conflict rules. Existing
  cached groups can still be used offline to add items.
- A tap skips every matching item already on the list, whether active or
  checked. Do not use ordinary `item.add` for group members: it restores
  checked items. Add a retry-safe `item.add_if_absent` operation that checks
  case-insensitive identity inside the server write transaction and returns
  `skipped` without changing an existing row; add only when no match exists.
  Filter the current optimistic list first, then queue remaining names in group
  order. Server-side checking is still required for offline replay and races
  with other users. Each member remains its own write, not an all-or-nothing
  batch; show any partial failure rather than claiming the whole group was added.

## Dependencies and tests

This is a new server-side entity, unlike usual-item suggestions. Likely seams:
`src/database_setup.py`, `src/database_crud.py`, `src/api/ops.py` or a room API
route, the room changes feed in `src/api/changes.py` and
`frontend/src/lib/data/room-store.svelte.ts`, plus snapshot validation/storage,
optimistic state and queue interfaces in `frontend/src/lib/data/`. Add the new
`item.add_if_absent` operation to API types, validation, optimistic projection
and queue replay. Check the existing transaction, change-sequence and
request-idempotency rules ([API writes](../docs/api-lists-items.md)).

Test room isolation and authorization, validation and live feed updates; test
that group addition skips both active and checked matches without changing
state or add counts, adds missing names in order, and handles concurrent or
replayed duplicates without restoring them. Test cached group use offline and
server-side skip on replay in `frontend/src/lib/data/offline-integration.test.ts`.

## Questions for Lead

- Confirm room-wide reusable groups rather than per-list or device-local groups,
  and confirm that public-share-only users cannot see or edit the room catalog.
- Is partial completion acceptable, or is one atomic all-or-nothing server
  write required? The proposal keeps per-item operations and reports partial
  failures.
- Confirm that group management may require a connection even though adding a
  cached group can work offline.

## Progress

- [x] Planned: proposed storage scope, access boundary, skip-all-existing
  semantics, offline behavior, dependencies and tests described.
- [ ] Implemented: group storage, feed, management and add action.
- [ ] Verified: authorization, live updates, partial results and offline replay.
