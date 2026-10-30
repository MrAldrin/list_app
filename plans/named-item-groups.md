# Named item groups

Lifecycle: temporary

## Outcome

Implement named item groups as authorized in the
[feature decision](../plans/decisions-for-heming.md#5-feature-priorities).
The first version stores reusable item names only; no quantities, notes or tags.

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
- A tap checks the current optimistic list state, skips matching active items,
  and sends the remaining names through the ordinary `item.add` path in group
  order. A checked matching item follows the existing add-or-restore behavior
  and is unchecked. Each item remains its own retry-safe, offline-queued write;
  this is not an all-or-nothing batch. Show any partial failure rather than
  claiming the whole group was added. A concurrent add is handled by the
  existing `duplicate_active` rejection.

## Dependencies and tests

This is a new server-side entity, unlike usual-item suggestions. Likely seams:
`src/database_setup.py`, `src/database_crud.py`, `src/api/ops.py` or a room API
route, the room changes feed in `src/api/changes.py` and
`frontend/src/lib/data/room-store.svelte.ts`, plus snapshot validation/storage,
optimistic state and queue interfaces in `frontend/src/lib/data/`. Check the
existing transaction, change-sequence and request-idempotency rules before
choosing group write operations ([API writes](../docs/api-lists-items.md)).

Test room isolation and authorization, validation and live feed updates; test
that adding a group skips active names, restores checked ones, preserves order,
handles concurrent duplicates and reports partial failures. Test cached group
use offline and replay of its individual `item.add` operations in
`frontend/src/lib/data/offline-integration.test.ts`.

## Questions for Lead

- Confirm room-wide reusable groups rather than per-list or device-local groups,
  and confirm that public-share-only users cannot see or edit the room catalog.
- Does “skip items already on the list” include checked items? This plan
  proposes restoring checked matches, like ordinary add. Is partial completion
  acceptable, or is one atomic all-or-nothing server write required?
- Confirm that group management may require a connection even though adding a
  cached group can work offline.

## Progress

- [x] Planned: proposed storage scope, access boundary, add semantics, offline
  behavior, dependencies and tests described.
- [ ] Implemented: group storage, feed, management and add action.
- [ ] Verified: authorization, live updates, partial results and offline replay.
