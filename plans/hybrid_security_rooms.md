# Plan: Hybrid Multi-Room Security

This plan describes the implementation of a "Multi-Lobby" system. It allows different users (you, your partner, friends) to have their own private "spaces" for lists, protected by a master gate and individual room passwords.

## The Concept
1. **The Front Gate:** A single global password protects the entry to the app.
2. **The Lobby:** Once inside, you can see existing room names (but not their contents) or create a new room.
3. **The Room:** Each room is a separate space for lists. To enter a room, you need that room's specific password.
4. **Persistence:** Once you enter a room, the app "remembers" you via cookies. You can pin the room to your home screen and jump straight in for ~30 days.

## Phase 1: Database Evolution
We need to update our SQLite structure to support "Ownership."
- **New Table: `rooms`**
    - `id` (Primary Key)
    - `name` (e.g., "The Johnsons")
    - `slug` (URL-friendly name, e.g., "the-johnsons")
    - `password_hash` (Securely stored password)
- **Updated Table: `lists`**
    - Add `room_id` column to link each list to a specific room.

## Phase 2: The Routing System
We will change how the URLs work:
- `/` -> The Front Gate (Login)
- `/lobby` -> The Room Selection/Creation screen.
- `/room/{slug}` -> The private space for that room's lists.
- `/room/{slug}/list/{id}` -> A specific list inside a room.

## Phase 3: Security Implementation (NiceGUI)
1. **Authentication Middleware:** A function that checks: "Is this user allowed to see this page?"
2. **Session Storage:** Use `app.storage.user` to store:
    - `is_authenticated`: True if they passed the Front Gate.
    - `authorized_rooms`: A list of room slugs they have successfully entered.

## Phase 4: User Interface
- **Login Page:** A simple, clean password prompt.
- **Room Selection:** Cards showing room names and an "Enter" button that triggers a password prompt.
- **Room Creation:** A dialog to set the Name and Password for a new space.

---

## Progress Tracking
- [ ] Research: Finalize database schema changes.
- [ ] Phase 1: Update `database_crud.py` with `rooms` table.
- [ ] Phase 2: Implement URL routing for `/lobby` and `/room/{slug}`.
- [ ] Phase 3: Add Master Password gate.
- [ ] Phase 4: Add Room-specific password checks.
- [ ] Phase 5: Migration (Move existing lists into a "Default" room).
