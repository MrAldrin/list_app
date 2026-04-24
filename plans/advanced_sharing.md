# Plan: Advanced Sharing (Tokens & Cross-Room Pinning)

This plan extends the "Hybrid Multi-Room" system to allow sharing individual lists with friends who might not have access to your entire room.

## The Concept
1. **Secret Share Links:** Every list gets a unique, unguessable "Share Token". Anyone with the link can view/edit that specific list.
2. **Access Control:** Visiting a share link does NOT grant access to the rest of the Room's lists.
3. **Cross-Room Pinning:** If a user has their own Room, they can "Pin" a shared list from someone else into their own dashboard for quick access.

## Phase 1: Database Updates
We need to track how lists are shared and who has pinned what.
- **Update Table: `lists`**
    - Add `share_token` (A unique random string, e.g., `uuid`).
- **New Table: `room_shared_lists` (The "Pin" table)**
    - `room_id` (The room that wants to see the list)
    - `list_id` (The actual list being shared)
    - *This allows one list to appear in multiple rooms.*

## Phase 2: The Sharing Route
- `/share/{token}` -> A public route that shows a single list.
- **Logic:** 
    - No password required for this specific URL.
    - If the user is already logged into a different Room (checked via cookies), show a "Return to my Room" button.

## Phase 3: The "Pin" Workflow
1. User A sends User B a link: `listapp.com/share/abc-123`.
2. User B opens the link. The app detects User B is logged into their own room "The Bakers".
3. The app shows a button: **"Add to 'The Bakers' Dashboard"**.
4. If clicked, a row is added to `room_shared_lists`.
5. Now, when User B goes to `/room/the-bakers`, both their own lists AND User A's "abc-123" list appear.

## Phase 4: UI Enhancements
- **Share Button:** Inside a list, add a button to "Copy Share Link".
- **Shared Indicator:** On the Room dashboard, show a small icon (e.g., 🔗) next to lists that are "Pinned" from other rooms so you know they aren't "yours".

---

## Progress Tracking
- [ ] Phase 1: Update `database_crud.py` with `share_token` and `room_shared_lists`.
- [ ] Phase 2: Create the `/share/{token}` page logic.
- [ ] Phase 3: Implement the "Pin to my Room" backend logic.
- [ ] Phase 4: Update `item_list` to handle shared/pinned context.
