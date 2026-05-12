# Subplan 5: Room UI Isolation & Smart Admin Navigation

This plan addresses the UI flow from a standard user's perspective to ensure the "illusion" of a standalone app is maintained, while still keeping it convenient for the Admin.

## The Problem
Currently, inside a Room Dashboard (`/room/{slug}`), there is a "Back" arrow pointing to `/` (the Admin Lobby). 
- For a normal user (e.g., Steve), this button is confusing. If he clicks it, he hits the Admin Login wall, which breaks the illusion that "Steve's Room" is his own private app.
- For the Admin, the button is convenient to return to the Lobby to manage other rooms.

## Options Considered

### Option 1: Remove the Button Completely
We simply delete the back arrow. 
- **Pros:** Perfect isolation for the user. They only see their room.
- **Cons:** As the Admin, to manage another room, you would have to manually click your browser's URL bar and delete the `/room/slug` part to get back to `/`.

### Option 2: The "Smart" Back Button (Recommended)
We can actually have the best of both worlds by conditionally hiding the button based on the user's browser cookies!

When *you* (the Admin) log in through the Front Gate (`/login`), the app sets a specific cookie: `app.storage.user['authenticated'] = True`.
When *Steve* logs into his room, he only gets his room slug added to `app.storage.user['authorized_rooms']`. He **never** gets the `authenticated` flag.

**The Logic:**
On the Room Dashboard, we check:
`if app.storage.user.get("authenticated", False):`
- **If True (Admin):** Render the "Back" arrow to the Lobby.
- **If False (Normal User):** Do not render the arrow. For them, the Room Name is aligned to the left, and it looks exactly like the root of a standalone app.

## Why Option 2 is Perfect
- **For Steve:** He opens his pinned app. There is no back button. It is just his lists. He has no idea the Lobby exists.
- **For You:** You log into the Lobby, click on Steve's room to help him with something, and you get a convenient Back arrow to return to your Lobby. 

## Implementation Plan
1. Open `src/main.py` and locate the `@ui.page("/room/{slug}")` function.
2. Find the header rendering section where the `arrow_back` icon is drawn.
3. Wrap the button in a simple `if` statement checking the `authenticated` flag from `app.storage.user`.

Does this "Smart Button" approach sound like the perfect balance between user illusion and admin convenience?

---

## Progress Tracking
- [x] Phase 1: Implement conditional rendering of the "Back" arrow in `room_page` based on `app.storage.user.get("authenticated", False)`.