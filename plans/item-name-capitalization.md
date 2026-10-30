# Preserve capitalization in item names

Lifecycle: temporary

## Outcome

Implement Heming's [decision](../plans/decisions-for-heming.md#2-capital-letters-in-item-names)
to show the case people entered while treating case-only names as duplicates.
Names remain trimmed. Room and list naming are out of scope.

**State:** Planned only. No implementation or feature verification has been done.

## Plan

- At this base the schema is at migration 11. Append a new migration (recheck
  the latest number when implementation starts); do not edit deployed
  migrations. Add a normalized duplicate key for each item, populated from its
  trimmed name with Python `lower()`, and enforce uniqueness per list with an
  index. This avoids relying on SQLite `NOCASE`/`lower()`, which only handle
  ASCII case. Preserve each existing `name` exactly during migration.
- Before creating the unique index, find any existing rows with the same key.
  Do not merge, rename or delete them automatically: raise a clear migration
  error and leave the transaction rolled back. The migration runner already
  makes a verified pre-migration backup and applies migrations atomically.
  Backfill the key without marking every item as a user edit in the change feed;
  retain/recreate change-tracking triggers if the implementation must suspend
  them during backfill.
- Update the item field-rule triggers in the new migration so they no longer
  reject capital letters. Keep the other field rules. Update `item.add`,
  `item.edit` and `item.restore` normalization and duplicate checks to preserve
  trimmed display text and use the key consistently; stale edit comparisons
  must still distinguish a different requested capitalization.
- Update the frontend's add/edit normalization and optimistic overlay so new
  queued item names retain case, while suggestions and duplicate checks remain
  case-insensitive. Do not rewrite existing queued op bodies or IDs: old queued
  lowercase names cannot recover the original text. Bump the server and client
  API version together because the meaning of item-name writes changes; follow
  [the API version rule](../docs/api.md#api-version).

## Dependencies and tests

Main seams: `src/database_setup.py` (`_FIELD_RULES`, migration list),
`src/database_crud.py` (`normalize_item_name`, add/restore/edit),
`src/api/ops.py` (`_item_name` and item handlers), and
`frontend/src/lib/data/overlay.ts` / `frontend/src/lib/list/items.ts`.

Add migration tests for preserving rows, unique-key collision rollback,
unchanged schema version after failure, and trigger behavior. Extend
`tests/test_api_item_ops.py` for add/edit/restore casing, duplicates and
changed-meanwhile casing; extend `frontend/src/lib/list/items.test.ts` and
`frontend/src/lib/data/add-count.test.ts` or the focused overlay tests for
preserved casing and duplicate projection. Verify replay of an old queued
lowercase op and current offline edits; the existing ordered queue and 30-day
hold rules remain unchanged ([offline rules](../docs/offline-viewing.md)).

## Questions for Lead

- The current app uses Unicode-aware `lower()`, not Unicode `casefold()`, while
  SQLite's index is ASCII-only. This plan proposes a Python-lower key to match
  current app behavior. Confirm that meaning of “case-insensitive” before the
  key format is fixed.

## Progress

- [x] Planned: migration, conflicts, offline/replay, compatibility and tests
  described from the current code.
- [ ] Implemented: database, API and frontend changes.
- [ ] Verified: migrations, API, offline replay and full relevant test suites.
