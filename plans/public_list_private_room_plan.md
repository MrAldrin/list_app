# Public Lists + Private Rooms Plan

## Problem Summary
You want two things at the same time:
1. A shared **list link** should be fully open (no room password required).
2. The **room page** should still require room password.

Right now, `/list/{slug}` still checks room authorization, so incognito users are blocked.
That defeats list sharing.

## Why the Old Guard Was Added
You previously saw a cross-user bug where one user action made another user session appear to enter a different room.
That bug came from UI refresh state leaking between clients, not from missing password checks on list links.
That UI refresh issue has now been fixed.

The extra room-auth check on `/list/{slug}` was added as a **safeguard** to reduce blast radius if a similar bug is reintroduced later.
That is a reasonable defense-in-depth idea, but it conflicts with the product requirement that list links must be truly public.

## Target Security Model (Simple Rules)
### Rule A: Room URLs are private
- `/room/{slug}` always requires valid room password (unless already authorized in that same browser session).
- Unauthorized users see inline room password prompt.

### Rule B: List URLs are public-by-link
- `/list/{slug}` is directly accessible to anyone with the link.
- No redirect to room password page when opening list link.

### Rule C: Room controls are never available from list-only access
- On list page, users can edit list items.
- But they cannot manage room-level features unless they authenticate for the room.

## Main Fix Strategy
## Phase 1: Remove room-auth gate on list route
In `src/main.py` `list_page(slug)`:
- Remove:
  - `auth_rooms = app.storage.user.get("authorized_rooms", [])`
  - `if room_slug not in auth_rooms: ... navigate.to("/room/{room_slug}")`

Effect:
- Shared list links work in incognito and home-screen PWA mode.

## Phase 2: Keep room boundary strong
In `room_page(slug)`:
- Keep current room-password gate.
- Keep room management actions (rename room, change password, delete room) only inside authenticated room page flow.

Effect:
- Visiting `/room/{slug}` from list Back button still asks for password if user is not authorized.

## Phase 3: Harden against cross-client state bleed
Treat this as a separate reliability/security boundary:
- Ensure refresh calls do not push one client’s room/list context into another client’s UI.
- Avoid global refresh behavior that can mutate `@ui.refreshable` target kwargs across sessions.
- Prefer per-page refresh triggers or explicit client/room-scoped update paths.

Effect:
- Prevents the original “friend edit changed my room context” class of bug.

Note:
- This is now the **primary safeguard** against regression.
- Route-level room auth on `/list/{slug}` should not be used as the primary safeguard because it breaks intended sharing behavior.

## Phase 4: Optional UX guard on list page
If user came via public list link and is not room-authorized:
- Replace Back button with the `ListR` logo (same pattern used on room screens for non-admin/non-back contexts).
- Only show Back button when user is room-authorized.
- Optional: show a small note:
  - “This is a shared list link. Room settings require room password.”

Effect:
- Reduces “I can go back into the room now” confusion for first-time users.
- Keeps room boundary behavior explicit without changing access rules.

## Test Plan
## Manual Scenarios
1. Browser A (authorized room owner) opens room and list.
2. Browser B incognito opens shared `/list/{slug}` directly.
3. Browser B can add/edit/check items in that list.
4. Browser B presses Back to `/room/{slug}` and is prompted for room password.
5. Browser B cannot access room management without password.
6. Browser A and B edits do not move each other into wrong room/list context.

## Automated Coverage (minimum)
1. Route behavior test for `/list/{slug}` without `authorized_rooms`:
- Renders list page (no redirect).
2. Route behavior test for `/room/{slug}` without `authorized_rooms`:
- Renders password prompt.
3. Regression test for cross-client refresh isolation (if feasible in current test setup).
4. Regression test that list access does not implicitly authorize room access:
- After opening `/list/{slug}` in a fresh session, `/room/{room_slug}` still prompts for password.

## Architecture Alignment
This plan aligns with current direction:
- Share-by-link collaboration at list level.
- Password protection at room boundary.
- Defense-in-depth through targeted refresh/session isolation tests (not by closing public list route).

No `ARCHITECTURE.md` change is required unless we want to explicitly document:
- “List links are public capability links.”

## Implementation Sequence
1. Remove list-route room auth gate.
2. Verify room-route gate still works.
3. Add/adjust tests for public list + private room behavior.
4. Run full test suite.
5. Manual two-browser verification.

## Progress Tracking
- [x] Define desired security model (public list, private room).
- [x] Identify root cause relationship to prior cross-user bug.
- [x] Draft implementation and verification plan.
- [x] Implement Phase 1 route change.
- [x] Implement Phase 4 header UX change (logo when not room-authorized).
- [ ] Add/adjust automated tests.
- [ ] Run manual two-browser verification.
