# Subplan 2: Multi-Room Architecture

This plan covers the second half of the security upgrade: allowing multiple separate "Rooms" (Workspaces). Each room will have its own password and its own set of lists, providing true separation between different groups of users (e.g., you and your partner vs. friends).

## Do We Need Another Database Migration in Production?
**Yes!** And just like before, we will write a script in `database_setup.py` that handles it automatically and safely on Railway.

Here is what the migration will do:
1. It will create the new `rooms` table.
2. It will automatically create a "Default Room" for your existing lists.
3. It will add a `room_id` column to the `lists` table.
4. It will link all your existing lists to the new "Default Room" so that none of your data is orphaned.

## Core Concepts
1. **The Global Gate (`/`):** The entry point is still protected by the `.env` `APP_PASSWORD`. This stops internet strangers from seeing your app or spamming it with fake rooms.
2. **The Lobby (`/` after login):** Shows a list of existing Rooms, and a button to create a new Room with a custom name and password.
3. **The Room Dashboard (`/room/{slug}`):** To enter a room, you must provide the Room's specific password. Once inside, you see the lists that belong *only* to that room. Like lists, Rooms get an unguessable URL (e.g., `/room/my-family-1a2b3c`).
4. **Shareable Lists (`/list/{slug}`):** Remains unchanged! You can still share a list directly via its unguessable URL.
5. **Smart "Back" Button:** On a list page, the "Back" button should now point to `/room/{room_slug}` instead of `/`. If an unauthorized friend clicks it, the middleware will trap them at the Room password prompt, keeping your other lists safe.
6. **Room Management:** You can rename your rooms. You can also delete them, but **deleting a room requires you to re-enter the room's password** as a strict safety measure. Deleting a room will cascade and delete all lists and items inside it.

## Phase 1: Database Evolution & Migration
- **Dependencies:** We will install `bcrypt` (`uv add bcrypt`) for industry-standard password hashing.
- **New Table: `rooms`**
    - `id` (INTEGER PRIMARY KEY)
    - `name` (TEXT NOT NULL)
    - `slug` (TEXT UNIQUE)
    - `password_hash` (TEXT NOT NULL)
- **Update Table: `lists`**
    - Add `room_id` (INTEGER) referencing `rooms.id` (ideally with `ON DELETE CASCADE` behavior handled in our CRUD logic).
- **Automatic Migration:** 
    - Create a "Default Room" (slug generated) with its password set to the current `.env` `GLOBAL_APP_PASSWORD`.
    - Add `room_id` to `lists`.
    - Update existing lists to point to the "Default Room".

## Phase 2: Backend Logic (`database_crud.py`)
- Add `get_rooms()`: Returns a list of all rooms (id, name, slug).
- Add `create_room(name, plain_password)`: Generates a slug, hashes the password via `bcrypt`, and inserts the room.
- Add `verify_room(room_slug, plain_password)`: Fetches the hash and verifies it via `bcrypt.checkpw`.
- Add `rename_room(room_id, new_name)`.
- Add `delete_room(room_id)`: Deletes all items, then lists, then the room itself.
- Update `get_lists(room_id)`: Only return lists for the specified room.
- Update `create_list(name, room_id)`: Save the list into the specified room.
- Update `get_list_details_by_slug(slug)`: Must now also return the parent `room_slug` so the UI knows where the "Back" button should go!

## Phase 3: The Lobby UI (`/`)
- Remove the "Add New List" and lists from the main `/` route.
- Replace it with a "Lobby" that shows:
    - The Global "Log out" button.
    - A list of buttons for available Rooms.
    - A "Create New Room" button (prompts for Name and Password).
- Clicking a Room button opens a password prompt dialog for that specific room. 
    - If successful, it adds the `room_slug` to `app.storage.user.get('authorized_rooms', [])` and redirects to `/room/{slug}`.

## Phase 4: The Room Dashboard UI (`/room/{slug}`)
- Create a new route `@ui.page("/room/{slug}")`.
- **Security Middleware/Check:** Verify that `slug` is in `app.storage.user.get('authorized_rooms', [])`. If not, redirect back to `/`.
- This page will have the "Add New List" button and display the lists for that room.
- Include a "Rename Room" and "Delete Room" button. The Delete action must prompt for the room password, verify it via the backend, and only then perform the deletion.

---

## Progress Tracking
- [ ] Phase 1: Install `bcrypt`, implement `rooms` table with auto-migration, update `lists` table.
- [ ] Phase 2: Add room functions to `database_crud.py` and update list functions to return `room_slug`.
- [ ] Phase 3: Build the Lobby UI at `/` to show/create rooms and handle room unlocking.
- [ ] Phase 4: Build the Room Dashboard at `/room/{slug}` with secure session checks, Rename/Delete controls, and update the List View's "Back" button.