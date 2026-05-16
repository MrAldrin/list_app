# Room Isolation Bug: Cross-User Room Mix-Up

## Problem Summary
You observed this behavior:
- Friend adds a list in their room, and your partner suddenly sees friend data.
- You add a list in your room, and friend suddenly sees your data.

This is a real room-isolation bug in the UI refresh flow.

## Why This Happens (Simple Explanation)
Think of each browser tab as a different person.
When one person updates something, we should only refresh:
- their own page, and
- other people in the same room.

Right now, one global refresh function is reusing one person’s room arguments for everyone.
So other connected users can get re-rendered with the wrong room context.

## Confirmed Root Cause
### 1. Global refresh is mutating all `list_of_lists` targets
In [`src/main.py`](/home/hsa/projects/list_app/src/main.py:124), `broadcast_updates` does this:
- `list_of_lists.refresh(room_id=room_id, room_slug=room_slug)`

`list_of_lists` is a `@ui.refreshable` function (see [`src/main.py`](/home/hsa/projects/list_app/src/main.py:130)).

In NiceGUI internals (local package code), refresh runs across all targets and updates stored args:
- [`refreshable.py`](/home/hsa/projects/list_app/.venv/lib/python3.13/site-packages/nicegui/functions/refreshable.py:112)
- `target.args = args or target.args`
- `target.kwargs.update(kwargs)`

So a refresh with `room_id` / `room_slug` can overwrite target kwargs for other clients too.

### 2. This violates intended architecture
`ARCHITECTURE.md` says updates should affect connected users in the same room.
Current behavior can cross room boundaries, so implementation is currently out of alignment with architecture.

## Secondary Risk Found
In [`src/database_setup.py`](/home/hsa/projects/list_app/src/database_setup.py:32), `lists.name` is globally unique (`name TEXT NOT NULL UNIQUE`).
But the app logic is room-scoped (same list name should be allowed in different rooms).

This is not the cause of the room mix-up, but it can cause incorrect constraints and future confusion.

## Fix Strategy
### Step 1: Stop global argument overwrite
Replace current broad refresh approach with room-scoped refresh logic.

Practical options:
1. Convert room page into a per-page refreshable container/method and refresh only that page instance.
2. Use explicit client-targeted updates (track room slug in per-client storage and refresh only matching clients).
3. Remove parameterized `list_of_lists.refresh(...)` from global broadcaster and trigger refresh from local room context only.

For MVP safety, option 3 is fastest.

### Step 2: Keep list-page refreshes scoped too
`item_list.refresh()` is currently global in `broadcast_updates`.
It should also be scoped (at least by current list, ideally by room/list ownership).

### Step 3: Add guardrails in UI routes
On `/list/{slug}`, verify that user is authorized for that list’s `room_slug` before rendering list contents.
This prevents accidental cross-room visibility if navigation/routing state goes wrong.

### Step 4: Fix DB constraint for multi-room correctness
Schema target for lists:
- Remove global unique on `lists.name`
- Add composite uniqueness `(room_id, name COLLATE NOCASE)` via index/migration

This aligns storage with room-based design.

## Verification Plan
1. Open Room A in Browser 1 and Room B in Browser 2.
2. Add list in Room A.
3. Confirm Browser 2 stays in Room B and sees no Room A list changes.
4. Add list in Room B.
5. Confirm Browser 1 stays in Room A and sees no Room B changes.
6. Repeat with both users on list pages.
7. Check duplicate list names:
- Allowed across different rooms.
- Blocked inside same room.

## Suggested Tests
- Unit/integration test for room-isolated list retrieval + creation behavior.
- UI-level test (or minimal regression harness) for cross-client room refresh isolation.

## Implementation Sequence
1. Refactor `broadcast_updates` so it no longer pushes room kwargs to all refreshable targets.
2. Scope `item_list` refresh behavior.
3. Add `/list/{slug}` authorization check against `authorized_rooms`.
4. Add DB migration for `(room_id, name)` uniqueness and remove global name uniqueness.
5. Run/extend tests.

## Progress Tracking
- [x] Reproduce conceptually from code path.
- [x] Identify root cause in `broadcast_updates` + NiceGUI refresh semantics.
- [x] Document architecture misalignment.
- [x] Define safe fix strategy.
- [x] Implement code changes.
- [ ] Validate with two-browser manual test.
- [x] Add/adjust automated tests.
