# Multi-List Feature Plan (Step by Step)

## Goal
Add support for multiple shopping lists in the same app, with:
- a selector at the top to switch active list
- a way to create new lists
- item actions (add/edit/delete/toggle/filter) scoped to the selected list

This plan is written for the current NiceGUI + SQLite codebase in `src/main.py`.

## Scope for this first version
- Shared list catalog for all users (no login, no permissions yet)
- Up to 4 concurrent users
- Real-time refresh can remain global at first (optimize later)
- Mobile-first UI behavior preserved

## Phase 0: Safety and preparation
1. Confirm app runs and current features work before starting migration.
2. Keep checking in changes incrementally with JJ while implementing phases.

## Phase 1: Database schema changes
1. Add a `lists` table:
   - `id INTEGER PRIMARY KEY`
   - `name TEXT NOT NULL UNIQUE`
2. Add a `list_id` column to `items`.
3. Set up a migration strategy for existing rows:
   - create default list row, e.g. `"default"`
   - assign all existing `items` to this default `list_id`
4. Enforce referential link:
   - `items.list_id` references `lists.id`
5. Add helpful index:
   - index on `items(list_id, done, name)`

Notes:
- SQLite does not always support all `ALTER` paths directly; if needed, create a new `items` table and copy data over.
- Keep migration idempotent where possible (safe to rerun).

## Phase 2: Data access helpers
1. Add helper to get all lists (sorted by name).
2. Add helper to create list by name (normalized input, duplicate guard).
3. Update item read helper to accept `list_id`.
4. Update add/restore logic to query only inside selected list.
5. Update edit/delete/toggle SQL to include selected `list_id` context where relevant.

Definition of done:
- No item query should run without explicit list scope (except migration/admin helpers).

## Phase 3: Per-client selected list state
1. Introduce a way to track active list per connected client/tab.
2. Initialize selected list on page load:
   - if lists exist, choose first/default
   - if none exist, create default and select it
3. Ensure selected list is available to all handlers on that page:
   - add
   - filter suggestions
   - edit rename
   - delete
   - toggle done

Implementation hint:
- Keep selected-list state near page construction (`index()`), not as one global shared variable.

## Phase 4: UI additions
1. Add top-row controls:
   - list selector dropdown
   - “new list” button/icon
2. Create “new list” dialog:
   - input for list name
   - save + cancel actions
   - validation (not empty, not duplicate after normalization)
3. On list selection change:
   - reload items for that list
   - refresh visible item list
4. Keep mobile layout as-is

## Phase 5: Wire existing item features to selected list
1. `sync_data` becomes list-aware (accepts `list_id`).
2. `broadcast_updates` should refresh views correctly:
   - MVP: refresh all clients
   - Better: refresh only clients currently viewing that `list_id`
3. Update add/search behavior:
   - history/suggestions from selected list only
   - max 3 hits behavior preserved
4. Update rename:
   - duplicate check within same list
5. Update toggle/delete:
   - only affect item in selected list
   - practical reason: after introducing multiple lists, every feature should be list-scoped by design, not by accident
   - optional defensive SQL pattern: `WHERE id = ? AND list_id = ?` for mutations

## Phase 6: Real-time behavior options
### Option A (fastest MVP, chosen now)
- Keep global refresh to all clients after any change.
- Each client re-renders based on its own selected list.

### Option B (cleaner, later)
- Track each client’s selected `list_id`.
- Broadcast only to clients viewing the changed list.


## Phase 7: Validation and manual test checklist
Run these tests after implementation:
1. Create a second list; confirm selector shows both lists.
2. Add item in list A; verify it does not appear in list B.
3. Rename item in list A to same name as item in list B:
   - should be allowed if duplicates are only blocked within a list.
4. Toggle/done item in list A; verify list B unchanged.
5. Delete item in list A; verify list B unchanged.
6. Open two tabs:
   - same list selected in both tabs -> live updates visible
   - different lists selected -> no cross-list contamination
7. Mobile test:
   - selector usable without awkward full-screen dialog behavior
   - add/search and notifications still usable with keyboard open

## Phase 8: Cleanup and small refactor pass
1. Move DB helpers to `src/database.py` (if you decide to follow planned structure).
2. Move schema/model helpers to `src/models.py`.
3. Keep `main.py` focused on UI composition and event wiring.
4. Remove dead globals (`refresh_callbacks` if unused).
5. Add comments for list scoping rules to prevent regressions.

## Risks and mitigations
- Risk: Accidentally mixing global and per-client selected state.
  - Mitigation: keep selected list in page-local/client-local flow.
- Risk: Duplicate logic across add/edit paths.
  - Mitigation: keep and reuse normalization + duplicate-check helpers.

## Suggested delivery breakdown (small PRs/commits)
1. Schema migration + default list bootstrap.
2. List selector + create-list dialog (UI only).
3. List-scoped reads and add flow.
4. List-scoped edit/delete/toggle + filter suggestions.
5. Real-time refinement (optional list-targeted broadcast).
6. Final test pass and docs update.

