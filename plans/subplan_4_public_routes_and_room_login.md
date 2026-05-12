# Subplan 4: Public Room Links & Inline Room Login

This plan outlines the architectural correction to make Room URLs truly shareable and independent of the Global Admin Password, fixing the flaw where users were wrongly redirected to the Admin Lobby.

## The Design Flaw (Current State)
Right now, the `GLOBAL_APP_PASSWORD` acts as a giant wall protecting *both* `/` (the Lobby) and `/room/{slug}` (the Room). If a user clicks a shared room link but hasn't entered the Room Password yet, the app redirects them to `/`, forcing them to encounter the Admin Login screen.

## The Correct Flow (Target State)
1. **The Admin Lobby (`/`):** The only page protected by the `GLOBAL_APP_PASSWORD`.
2. **The Room Page (`/room/{slug}`):** A public URL. Anyone can visit it. However, if they haven't authenticated for *that specific room*, the page simply renders an inline "Enter Room Password" box instead of redirecting them away.
3. **The List Page (`/list/{slug}`):** A completely public URL. Anyone with the link can edit the list without any password. If they click the "Back" button, they go to the Room Page (`/room/{slug}`), where they will be met with the inline Room Password prompt (if they don't already have access).

## Phase 1: Loosen the Global Middleware
We need to update the `auth_middleware` in `src/main.py` so it only protects the root Admin Lobby.
- **Current:** `if path == "/" or path.startswith("/room/"):`
- **New:** `if path == "/":`

## Phase 2: Inline Room Login
We will modify the `@ui.page("/room/{slug}")` function.
- Currently, if the user doesn't have access to the room in their cookies (`slug not in auth_rooms`), it redirects to `/`.
- **New Logic:** 
    - Fetch the room details from the database (to ensure the room exists and to get its name).
    - Check if `slug in auth_rooms`.
    - **If YES:** Render the normal Room Dashboard (lists, "Add New List", etc.).
    - **If NO:** Render a simple Login Card directly on the page asking for the "Room Password".
    - When they submit the password, verify it using `verify_room(slug, password)`. If correct, add the slug to their `authorized_rooms` cookie and refresh the page to reveal the dashboard.

## Phase 3: Update List "Back" Button
The List Page (`/list/{slug}`) is already public.
- The "Back" button currently navigates to `/room/{room_slug}`.
- Because of Phase 1 and 2, when an unauthorized user clicks "Back", they will safely land on the Room Page and see the "Enter Room Password" prompt, completely isolated from the Admin Lobby!

---

## Progress Tracking
- [x] Phase 1: Update `auth_middleware` to only protect `/`.
- [x] Phase 2: Implement the inline password prompt on the `/room/{slug}` route.
- [x] Phase 3: Verify the "Back" button flow from a List Page behaves correctly.