# Plan: Handle Deleted Lists for Other Users

## Goal

When a list is deleted while another user is viewing it, the viewer should see a clear unavailable-list screen instead of an apparently empty, unusable list.

The behavior should be:

- **User still has room access:**
  - Message: `This list was deleted.`
  - Show a `Back to room` button.
- **User does not have room access:**
  - Message: `This list was deleted or you no longer have access.`
  - Do not show a room button.
- The same unavailable-list layout should be used for both cases.
- A direct link to an already missing list should use the safe generic message, because the server cannot know whether the list was deleted or the URL is invalid.

## Design decision

Use lightweight server-side polling from the list page rather than adding a new websocket/event-bus system.

The app currently uses NiceGUI refreshable components and SQLite, and the architecture targets only a few simultaneous users. A two-second existence check is simple, works across browser tabs and app processes, and avoids introducing new infrastructure. It is near-real-time rather than instantaneous, which is sufficient for this MVP.

No database schema change is needed. A missing list row is already the source of truth.

## Current behavior to account for

- `src/main.py:list_page` loads list details once and then renders the list UI using the numeric `list_id`.
- `item_list` queries items by `list_id`; after deletion this produces an empty list.
- `broadcast_updates()` currently refreshes both room lists and item lists. A list deletion must not refresh the stale `item_list`, because that creates the misleading empty-list state before the deletion screen appears.
- Room access is currently determined from a validated room token in `localStorage`, not from the cached `authorized_rooms` value. The new behavior must preserve that security model.

## Implementation phases

### Phase 1: Define the unavailable-list state and presentation

1. Add a small list-page state model in `src/main.py` (a typed dictionary or dataclass is sufficient) with at least:
   - active/unavailable status;
   - list slug and room slug;
   - the previously known list name, when available;
   - the room-access context needed to decide whether to show `Back to room`.
2. Extract a reusable renderer for the unavailable state, for example `_render_unavailable_list(...)`.
3. Render it inside the existing mobile-sized page card so the page does not navigate away unexpectedly.
4. Use the two messages above:
   - validated room access: specific deletion message and `Back to room`;
   - no validated room access: privacy-preserving generic message and no button.
5. Make the unavailable state replace the entire active list UI:
   - header actions disappear;
   - add input disappears;
   - item editing, tags, undo, and delete controls disappear;
   - no further list mutations can be initiated from the screen.
6. Keep the initial `not found` route safe and generic. It has no list details from which room access can be validated, so it should not show a room button.

### Phase 2: Detect deletion while the page is open

1. Refactor the active portion of `list_page` into a container that can be cleared and replaced without changing the URL.
2. Start a `ui.timer` for the active list page with an initial interval of approximately two seconds.
3. On each tick, call `get_list_details_by_slug(slug)` rather than querying only by the old numeric ID. This prevents a deleted list from being treated as an empty list.
4. If the slug still exists, do nothing and allow the normal refreshable item UI to operate.
5. If the slug no longer exists:
   - mark the page unavailable exactly once;
   - stop/cancel the timer;
   - determine whether the current room token is still valid;
   - replace the active UI with the appropriate unavailable screen.
6. If the room no longer exists as well, do not show a `Back to room` button even if the original list page had room access. This avoids linking to a dead room.
7. Treat temporary database-read failures as retryable rather than as proof that the list was deleted. The timer should try again and leave the current UI intact.

### Phase 3: Prevent stale writes and race-condition errors

The timer may take up to the polling interval to notice deletion, so callbacks must also be safe during that window.

1. Add a shared list-availability check for list-page callbacks.
2. Before an action starts, reject it if the page has already transitioned to unavailable.
3. Cover all list mutations, not only adding an item:
   - add or restore item;
   - toggle done state;
   - edit item name/description;
   - change quantity;
   - delete item;
   - add/delete tags;
   - undo item/tag changes.
4. Add a domain-level `ListNotFound`/`ListUnavailable` error or an equivalent explicit result for service/database writes that target a deleted list.
5. Ensure a race between a write and deletion is handled cleanly:
   - do not display a raw SQLite/traceback error;
   - transition the page to the unavailable screen;
   - do not claim that an item was added or changed if the write did not happen.
6. Keep the existing room-token authorization checks unchanged. This feature must not turn a list page into a way to regain room access.

### Phase 4: Adjust deletion refresh behavior

1. In both list deletion paths in `src/main.py` (admin and room-token deletion), continue refreshing the room’s list-of-lists.
2. Change the post-delete update call to avoid refreshing `item_list` globally, e.g. use `broadcast_updates(refresh_lists=True, refresh_items=False)`.
3. Let open list pages detect deletion through their existence timer and render the unavailable state.
4. Keep the existing success notification for the user who performed the deletion.
5. Verify that deleting a list still removes its items and removes the list from the room page.

### Phase 5: Extract small testable helpers

To keep UI tests manageable, isolate pure decisions where practical:

- choosing the unavailable message from current room-access state;
- deciding whether the room button is allowed;
- transitioning once from active to unavailable;
- distinguishing a missing list from a transient database error.

Avoid making tests depend on exact NiceGUI component internals wherever a pure helper can be tested instead.

## Tests to add or update

### Database/service tests

- A deleted list no longer has details when looked up by slug.
- Item/list mutation helpers fail with the expected domain result when the list has already been deleted.
- A failed mutation does not report success or create an orphan item.
- Existing list deletion tests continue to verify that items are removed.

### UI/state tests

- An open list with valid room access chooses the specific deletion message and exposes the room action.
- An open public-link list without room access chooses the generic message and exposes no room action.
- An initially missing/direct list URL uses the generic message.
- A second polling tick does not render the unavailable state twice.
- A transient database error does not incorrectly mark the list as deleted.

### Manual multi-user checks

1. Open the same list in two browser sessions.
2. Give both sessions room access; delete the list from one session.
3. Confirm the other session changes to the unavailable screen within the polling interval and shows `Back to room`.
4. Open the same list through a public link without room access; delete it from a room-authorized session.
5. Confirm the public-link session gets the generic message and no room button.
6. Click `Back to room` and confirm the user sees the room and its remaining lists.
7. Try to add/edit/toggle an item immediately before and after deletion; confirm there are no raw errors and no writes to the deleted list.
8. Refresh or reopen the deleted URL and confirm the generic unavailable screen.
9. Delete the last list in a room and confirm the room still renders correctly with no lists.
10. Delete a room while a list page is open and confirm the unavailable screen does not offer a dead room link.

## Files expected to change during implementation

- `src/main.py`
  - unavailable-list renderer and state transition;
  - list existence timer;
  - stale callback guards;
  - deletion refresh behavior.
- `src/item_service.py`
  - explicit deleted-list failure handling, if the service layer is used for the guards.
- `src/database_crud.py`
  - list existence/affected-row checks or a domain error boundary for deleted-list writes.
- `tests/test_item_service.py`
  - service-level deleted-list cases.
- `tests/test_database_crud.py`
  - database behavior needed for safe deletion races.
- Possibly a new `tests/test_list_deletion.py`
  - pure state/helper tests.

No change to `ARCHITECTURE.md` is expected: polling is an implementation detail within the existing NiceGUI + SQLite architecture.

## Completion criteria

- A user viewing a deleted list never remains on an empty, editable-looking list.
- The active controls disappear after deletion is detected.
- Room-authorized users see the specific deletion message and can return to the room.
- Other users see only the privacy-preserving generic message.
- Direct links, refreshes, concurrent actions, and room deletion fail safely.
- Python quality checks pass:

```bash
uv run ruff format .
uv run ruff check --fix .
uv run pytest -q
uv run ruff format --check .
uv run ruff check .
```

## Progress tracking

- [x] Phase 1: Define unavailable-list state and presentation.
- [x] Phase 2: Detect deletion while the page is open.
- [x] Phase 3: Prevent stale writes and race-condition errors.
- [x] Phase 4: Adjust deletion refresh behavior.
- [x] Phase 5: Add automated tests; manual multi-user checks are documented as not runnable in this environment.
- [x] Final: Run formatting, linting, and test checks.

### Verification note

The initial implementation passed automated tests and Python quality checks, but browser checks were not run during that implementation session.

### Review follow-up: reused list IDs

SQLite can reuse a deleted list's numeric ID. The original existence-only write guard could therefore allow a stale page to modify a replacement list.

- [x] Carry the original list slug through list-page writes, undo, and room/admin list rename/delete dialogs.
- [x] Verify that slug inside the same `BEGIN IMMEDIATE` transaction as the write; reject mismatches with `ListUnavailable` and roll back.
- [x] Stop stale item/tag refreshes and suggestions from treating a replacement list as the original.
- [x] Add regression coverage for database mutations, service forwarding, room-token actions, undo, rollback, and subsequent valid writes.
- [x] Keep the two-second timer and existing schema unchanged.
- [x] Final quality checks: 112 tests pass; Ruff formatting and lint checks are clean (one existing Starlette/httpx deprecation warning).
- [x] Run isolated browser checks with Chrome: stale add, item-edit, and room-delete callbacks after ID reuse leave replacement data untouched. Those stale-page timers were deliberately delayed to exercise callback protection rather than polling.
- [x] Run isolated browser checks with the real timer: deleting a room clears both authorized and public list pages and removes the room link.

The earlier review also verified ordinary list deletion messages, edit-dialog cleanup, last-list deletion, back navigation, and deleted-URL reloads in Chrome. These targeted checks do not replace every scenario in the full manual checklist above.
