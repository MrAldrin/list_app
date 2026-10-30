# Ordered aisle categories

Lifecycle: temporary

## Outcome

Implement ordered aisle categories as authorized in the
[feature decision](../plans/decisions-for-heming.md#5-feature-priorities).
Keep existing person-tag filters and behavior unchanged.

**State:** Planned only. No implementation or feature verification has been done.

## Plan

- Keep the existing `list.tags` (available person tags) and `item.tags`
  (person assignments) intact. Proposed separate data: an ordered
  `list.aisle_tags` array and one optional `item.aisle_tag`. This gives a list
  one shared store order without making tag sorting alter the existing person
  tag choices. Default existing lists to no aisle tags and existing items to no
  aisle assignment.
- Add UI to define, reorder and delete aisle categories, assign or clear an
  item's aisle in its edit flow, and choose an “Aisle order” view. Group visible
  items under aisle headings in configured order; show unassigned items last.
  Preserve current search, person-tag filtering, hide-checked rules, and
  open-before-checked behavior within each aisle. Keep the selected view local
  to the browser like the current item sort. Do not add multiple store profiles.
- Include aisle fields in API feeds and saved snapshots. Make assignment and
  reorder writes explicit desired-state operations so retries are safe, and
  project them in the existing offline overlay/queue. Keep category ordering
  intact in API and client code; unlike person tags, never alphabetize it.
  Removing a category must not silently erase assignments: require clearing or
  reassigning its items first, unless Lead chooses a different explicit rule.

## Dependencies and tests

Main seams: `src/database_setup.py`, `src/database_crud.py` and
`src/api/ops.py`; list/item feed shapes in `src/database_crud.py` and
`frontend/src/lib/data/types.ts`; snapshot validation, optimistic projection and
queue replay in `frontend/src/lib/data/`; list editing and grouping in
`frontend/src/lib/list/ListView.svelte`, `ListTags.svelte`, `ItemDialog.svelte`,
`visible-items.ts` and `frontend/src/lib/data/order.ts`. The list's existing
person-tag editor and row buttons are documented in
[API: lists and items](../docs/api-lists-items.md) and
[sorting items](../docs/item-sorting.md).

Test the migration defaults, ordered CRUD, assignment validation and safe
category removal; test aisle grouping with unassigned items, person filters,
search, checked visibility, and the existing row-hold behavior. Add snapshot,
optimistic update and offline replay tests for both assignment and reorder.

## Documentation updates after implementation

Update `docs/api-lists-items.md` with the separate aisle fields and write
behavior, keeping person tags distinct. Update `docs/item-sorting.md` with aisle
order, grouping, unassigned items, and the interaction with existing sorts.
Update `docs/offline-viewing.md` to include offline aisle assignment/reordering
and queued replay if those writes remain offline-capable as proposed.

## Questions for Lead

- Confirm one optional aisle per item (the proposal), rather than multiple aisle
  assignments, and one shared aisle order per list rather than per-device or
  multiple named store layouts.
- Confirm whether competing offline reorder writes may use last-write-wins or
  must be rejected as stale. The existing list tag/settings operations do not
  provide field-level conflict detection.
- Confirm the proposed rule that a category cannot be removed while items still
  use it, avoiding silent loss of assignments.

## Progress

- [x] Planned: separate data model, grouping behavior, offline/replay,
  dependencies, data-loss guard and tests described.
- [ ] Implemented: aisle data, controls, assignment and grouped view.
- [ ] Verified: migrations, tag boundaries, sorting/grouping and offline replay.
