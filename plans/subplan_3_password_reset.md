# Subplan 3: Room Password Management & Admin Override

This plan outlines how to handle forgotten passwords and routine password updates for Rooms, ensuring the administrator (you) can always retain control without compromising security and user trust.

## Core Concepts

1. **The Trust Model:** The `GLOBAL_APP_PASSWORD` (Admin Key) **cannot** be used to silently unlock or snoop inside a user's room. If an admin wants to gain access, they must forcefully reset the password. This guarantees that the user will immediately know because their old password will no longer work.
2. **Standard Reset (User Flow):** Users who pin their room to their homescreen will rarely see the Lobby. Therefore, they can change their password directly from inside the Room Dashboard (using their current room password).
3. **Admin Override (Recovery Flow):** If a user *forgets* their room password, they are locked out. The administrator can forcefully reset it from the main Lobby (`/`) using the Admin Key.

## Phase 1: Backend Logic (`database_crud.py`)
We need a way to update the password hash in the database.
- **Add `update_room_password(room_id, new_plain_password)`:** 
    - This function will use `bcrypt` to generate a new hash for `new_plain_password` and update the `password_hash` column for the given room.

## Phase 2: Security Verification Logic
We will have two distinct verification paths based on where the reset is happening:
- **Inside the Room (User):** Verifies the provided "Old Password" against the room's hash using `verify_room()`.
- **In the Lobby (Admin):** Verifies the provided "Admin Key" against the `.env` `GLOBAL_APP_PASSWORD`.

## Phase 3: The Lobby UI Updates (`/`) - Admin Recovery
- Add an "Admin: Reset Room Password" button in the Lobby (e.g., as an icon on the room cards).
- Clicking it opens a dialog:
    1. **Admin Key:** Input field for the `GLOBAL_APP_PASSWORD`.
    2. **New Password:** The new password for the room.
- On submit: If the Admin Key matches, update the password. If the user tries their old room password here, it will fail. This is strictly an admin recovery tool.

## Phase 4: Room Dashboard UI Updates (`/room/{slug}`) - User Reset
- Add "Change Password" to the existing three-dots menu inside the Room.
- Clicking it opens a dialog:
    1. **Current Password:** The input field to verify the user knows the current room password.
    2. **New Password:** The new password they want to set.
- On submit: Verify the current password via `verify_room()`. If correct, update the password hash.

---

## Progress Tracking
- [x] Phase 1: Add `update_room_password()` to `database_crud.py`.
- [x] Phase 2 & 3: Build the Admin Reset dialog in the Lobby (verifying against Global Password).
- [x] Phase 4: Add the User Change Password dialog to the Room Dashboard menu (verifying against current room password).