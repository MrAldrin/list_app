# Item Service Layer Plan

## Why This Plan Exists
Right now, `main.py` still contains some business rules (for example: what happens on duplicate item names, and when to restore a checked item instead of adding a new one).

That works, but it makes `main.py` do too many jobs:
- UI rendering
- UI event handling
- business decisions

This plan introduces `src/item_service.py` so the app is easier to understand and safer to change.

Simple idea:
- `main.py` = "what user clicked"
- `item_service.py` = "what should happen"
- `database_crud.py` = "how SQL is executed"

---

## Goals
1. Keep all list-scoped item rules in one place.
2. Reduce duplicate logic in UI callbacks.
3. Make behavior easier to test without running the full NiceGUI app.
4. Prevent regressions like cross-list or cross-tab contamination from scattered logic.

Non-goal:
- No database schema changes in this step.

---

## Current Structure (Before)
- `src/main.py`: UI + some business rules + calls into CRUD
- `src/database_crud.py`: SQL read/write helpers
- `src/database_setup.py`: DB setup/migrations/bootstrap

## Target Structure (After)
- `src/main.py`: UI composition, events, notifications, refresh calls
- `src/item_service.py`: item/list workflows and validation rules
- `src/database_crud.py`: low-level SQL operations only
- `src/database_setup.py`: DB setup and migrations

---

## Proposed `item_service.py` API (v1)

Use clear return values so UI can decide user messages.

### 1) Add or restore item
`add_or_restore_item(list_id: int, raw_name: str | None) -> tuple[str, str | None]`

Possible status values:
- `"invalid_name"`: empty/whitespace name
- `"added"`: brand new item inserted
- `"restored"`: item existed and was done, now restored
- `"duplicate_active"`: item already exists and is not done

Second return value:
- normalized item name (or `None` for invalid)

Why:
- This flow currently has branching in UI code.
- Moving it to service makes behavior consistent everywhere.

### 2) Rename item with validation
`rename_item_with_checks(list_id: int, item_id: int, raw_name: str | None) -> tuple[str, str | None]`

Possible status values:
- `"invalid_name"`
- `"duplicate_name"`
- `"renamed"`

Why:
- Keeps normalize + duplicate-check + rename as one unit.
- Prevents future routes from skipping validation accidentally.

### 3) Toggle done state
`toggle_item_done(list_id: int, item_id: int, done: bool) -> str`

Possible status values:
- `"updated"`

Why:
- Very small now, but gives a future extension point (audit log, permission checks, etc.).

### 4) Delete item
`delete_item_from_list(list_id: int, item_id: int) -> str`

Possible status values:
- `"deleted"`

Why:
- Same reason as toggle: one place for future checks.

---

## Design Rules for the Service Layer
1. Service functions must always require `list_id` for item mutations.
   - This enforces list scope by default.
2. Service functions should not call `ui.notify` or any NiceGUI APIs.
   - UI concerns stay in `main.py`.
3. Service functions should return status codes, not UI text.
   - Keeps service reusable and testable.
4. Keep CRUD helpers "dumb" and focused on SQL.
   - Validation and branching belong in service.

---

## Step-by-Step Implementation Plan

### Phase 1: Create `item_service.py`
Add service functions that call existing CRUD helpers:
- `add_or_restore_item(...)`
- `rename_item_with_checks(...)`
- `toggle_item_done(...)`
- `delete_item_from_list(...)`

No UI changes yet, just create the module and simple unit-level logic.

### Phase 2: Migrate `main.py` item handlers
Update UI callbacks to call service functions and switch on returned status.

Example areas:
- `add_to_list(...)`
- rename dialog save handler
- checkbox toggle handler
- delete handler

### Phase 3: Keep notifications in UI only
Map service statuses to `ui.notify(...)` messages inside `main.py`.

This keeps UI wording flexible while preserving central business logic.

### Phase 4: Cleanup
Remove now-unused direct business-rule helpers from UI path.
Keep `normalize_item_name` where it makes most sense (service or CRUD), but make one source of truth.

### Phase 5: Validate behavior manually
Run manual tests to ensure no behavioral regressions.

---

## Manual Test Checklist
1. Add a new item in selected list -> item is added.
2. Add same active item again -> duplicate warning path.
3. Check off an item, then add same name -> restored path.
4. Rename item to empty -> validation warning path.
5. Rename item to existing name in same list -> duplicate warning path.
6. Rename item to name that exists only in another list -> allowed.
7. Toggle item done in list A -> list B remains unchanged.
8. Delete item in list A -> list B remains unchanged.

---

## Risks and Mitigations
- Risk: creating a "service" that is just thin wrappers and adds noise.
  - Mitigation: only move real decision logic (validation/branching), not pure pass-through code.
- Risk: status strings get inconsistent.
  - Mitigation: define status constants (or Enum) once in `item_service.py`.
- Risk: accidental UI coupling inside service.
  - Mitigation: no NiceGUI imports in service module.

---

## Definition of Done
1. `item_service.py` exists and owns add/restore/rename/toggle/delete rules.
2. `main.py` uses service return statuses and no longer duplicates core item business rules.
3. `database_crud.py` remains SQL-focused.
4. Manual checklist passes.
5. Code remains easy to follow for a beginner.
