# Suggest usual items

Lifecycle: temporary

## Outcome

Use the existing times-added count as authorized in the
[feature decision](../plans/decisions-for-heming.md#5-feature-priorities).
Keep typed autocomplete unless the design below is approved; add no history,
accounts or server-side statistics.

**State:** Planned only. No implementation or feature verification has been done.

## Plan

- Build the suggestions from the current list's item feed. `add_count` already
  counts new items, restoring checked items and unchecking them; it is present
  in snapshots and in the API changes feed. It is a per-item, per-list count,
  not a person-specific history.
- Proposed MVP: when the add field is blank, show a compact “Usual items” row
  with up to three names whose count is at least two, ordered by count then
  case-insensitive name. Exclude active items; keep checked items eligible so
  tapping one uses the normal restore behavior. Typing continues to use the
  existing three-name autocomplete. A tap calls the existing `room.addItem`,
  so all writes retain normal duplicate, count and feedback rules.
- Use the snapshot's counts while offline. A cached checked item can be restored
  into the local view and its ordinary `item.add` is kept in the existing
  device-local queue, then replayed in order. No extra persistence or API field
  is needed. If the count changes on another device, the next feed refresh
  updates the ranking.

## Dependencies and tests

Main seams: `frontend/src/lib/list/items.ts` (`itemSuggestions`),
`frontend/src/lib/list/AddItem.svelte`, and the item data in
`frontend/src/lib/data/types.ts`. Backend count rules are in
`src/database_crud.py` and [the API contract](../docs/api-lists-items.md#operation-types).

Add pure-helper tests for threshold, ranking, stable ties, active-item exclusion,
checked-item inclusion and empty/typed input. Add component/browser coverage for
keyboard and touch access to the new buttons without changing the combobox
contract ([adding items](../docs/adding-items.md)). Extend
`frontend/src/lib/data/offline-integration.test.ts` to show that a usual item
uses the normal optimistic add and queued replay; no new server tests should be
needed unless the count contract changes.

## Questions for Lead

- Confirm the proposed “top three, count at least two, shown only when the field
  is blank” behavior. These are product choices; the existing count field alone
  does not determine a cutoff or placement.

## Progress

- [x] Planned: data source, offline behavior, interface seams and tests
  described from the current code.
- [ ] Implemented: usual-item ranking and accessible one-tap UI.
- [ ] Verified: count ranking, list behavior and offline replay.
