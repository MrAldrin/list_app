# Subplan 1: Single Room Global Password & Shareable Lists

This is the first step toward our full security architecture. Instead of building the entire multi-room system at once, we will start by securing the app as a "Single Room" application. 

This gives us immediate security (strangers can't see the dashboard or delete random lists) and teaches us the basics of authentication, without the complexity of managing multiple rooms.

## The Concept

1. **Global Password (The Dashboard Gate):** The main page of the app (the Dashboard where all lists are shown) is protected by a single, hardcoded password. 
2. **Shareable Lists:** When a list is created, it gets a unique, unguessable URL (e.g., `/list/groceries-a8f9b2`).
3. **The "Back" Button Security:** Anyone can visit a shareable list URL and edit that specific list without a password. However, if they click "Back to Dashboard", they are hit with the Global Password prompt.

## Phase 1: Database Updates (Future-Proofing & Migration)
Even though we only have "one room" conceptually right now, we will add the `slug` column to the `lists` table so our URLs become unguessable.
- **Update Table: `lists`**
    - Add `slug` (e.g., `groceries-a8f9b2`).
    - We *won't* add the `rooms` table just yet. We will treat the entire app as one global room for now.
- **Data Migration:**
    - Update `database_setup.py` to check if the `slug` column exists. If not, add it via `ALTER TABLE`.
    - Backfill any existing lists by generating a unique slug for them, so old data isn't lost and gets the new security model immediately.
    - *Note: We intentionally drop support for old `/list/{id}` URLs. Keeping integer-based routes active would defeat the unguessable slug security!*

## Phase 2: Security Implementation (NiceGUI & Env Vars)
1. **Environment Variables:**
    - Install `python-dotenv` if not already installed.
    - Create a `.env` file for local development (and add to `.gitignore`) with `APP_PASSWORD=...`.
    - Read `os.environ.get("APP_PASSWORD")` in the code, ensuring the password is never hardcoded or pushed to Git.
2. **Global Password Prompt:** Create a simple login page at `/login` that verifies against the `APP_PASSWORD`.
3. **Authentication Middleware:** Add a NiceGUI router check:
    - If a user tries to visit the Dashboard (`/`), check if they are logged in.
    - If not, redirect them to `/login`.
4. **Session Storage:** Use `app.storage.user` to remember that the user entered the correct password, so they don't have to enter it every time.

## Phase 3: Routing & List Sharing
1. **List URLs:** Change the list view route from `/list/{id}` to `/list/{slug}`.
2. **Unprotected List Route:** Ensure the authentication middleware allows anyone to visit `/list/{slug}` without the global password.
3. **The Back Button:** The "Back" button on the list page goes to `/`. The middleware will automatically block unauthorized users from seeing the dashboard.

---

## Progress Tracking
- [ ] Phase 1: Update `database_crud.py` and `database_setup.py` to support `slug` on lists.
- [ ] Phase 2: Setup `python-dotenv`, `.env`, and implement the Global Password login page and middleware.
- [ ] Phase 3: Update List creation to generate the `slug`.
- [ ] Phase 4: Update the List view to use the `slug` and allow public access.