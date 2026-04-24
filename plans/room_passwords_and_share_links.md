# Plan: Room Passwords & Shareable Lists

This plan outlines the implementation of a security model that protects your app from strangers, prevents shared-link users from snooping on your other lists, and sets up a future-proof database structure.

## Core Concepts

1. **The Room (Dashboard):** A space that holds multiple lists. To view a Room (and the lists inside it), you must know the Room's password.
2. **Shareable Lists:** Every list gets a unique, unguessable URL when created (e.g., `/list/groceries-a8f9b2`).
3. **The "Back" Button Security:** Anyone can visit a shareable list URL and edit that specific list without a password. However, if they click "Back to Dashboard", they are hit with the Room password prompt. They cannot see your other lists.

## Why this is Future-Proof (No Big Refactors)
By creating a `rooms` table in the database now, we are building the exact foundation needed for full user accounts later.
- **Today:** A "Room" is protected by a simple password.
- **Future:** We change the "Room" to belong to a specific "User Account". The database structure (`rooms` -> `lists` -> `items`) remains identical. We only change how we log in!

## Phase 1: Database Foundation
We will set up the tables to support this architecture permanently.
- **Table: `rooms`**
    - `id` (Primary Key)
    - `name` (e.g., "Home")
    - `password` (The password to view the dashboard)
- **Table: `lists`**
    - `id` (Primary Key)
    - `room_id` (Links the list to a room)
    - `name` (e.g., "Groceries")
    - `slug` (The unguessable string, e.g., `groceries-a8f9b2`)
- **Table: `items`**
    - `id`, `list_id`, `text`, `done`

## Phase 2: UI & Routing
1. **The Entry (`/`):** Asks you to select a Room (or create one) and enter its password.
2. **The Dashboard (`/room/{id}`):** Protected route. Checks if your browser cookie remembers the password. Shows all lists.
3. **The List View (`/list/{slug}`):** Unprotected route. Anyone with the link can view/edit the items. 

## Phase 3: The "Back" Button Logic
On the List View, the "Back" button points to `/room/{id}`. 
- If **you** click it, your browser has the cookie, so you see your dashboard.
- If a **friend** clicks it, they don't have the cookie, so they see: *"Please enter the password for this Room."*

---

## Progress Tracking
- [ ] Phase 1: Update `database_setup.py` and `database_crud.py` to include `rooms` and the list `slug`.
- [ ] Phase 2: Build the Room Login UI and password verification logic.
- [ ] Phase 3: Update List creation to generate the unique `slug`.
- [ ] Phase 4: Update the List View to be accessible via `slug` instead of `id`.