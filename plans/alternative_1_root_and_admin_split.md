# Plan: Alternative 1 (Public Root + Admin at Separate URL)

## Goal
Explain a simpler app flow where:
- Friends only use their own Room URLs.
- Admin tools live at a separate URL.
- iPhone Home Screen installs in Safari no longer bounce users to Admin password.

---

## The Core Idea (Simple Terms)
Right now, your app icon opens `/`, and `/` is protected by Admin password.
That creates the Safari problem.

Alternative 1 fixes this by changing responsibilities:
- `/` becomes a **public entry page** (not admin-protected).
- `/admin` becomes the **admin-only area** (password-protected).

So Home Screen open at `/` is always safe for regular users.

---

## Proposed URL Structure

### Public URLs (for everyone)
- `/` -> public landing page with simple actions
- `/room/{slug}` -> room page with room password prompt when needed
- `/list/{slug}` -> list page (your current sharing behavior)

### Admin URLs (only you)
- `/admin/login` -> admin login page
- `/admin` -> admin dashboard (create room, room management)

---

## What Should `/` Be?
It should be a **useful entry page**, not a blank placeholder.

Recommended content:
1. Small app title and short text: "Open your room link to continue."  
2. One input: "Enter Room Link or Room Code" (optional for MVP)  
3. A button: "Admin" -> goes to `/admin/login`  
4. Optional help text for iPhone users: "Add this to Home Screen"

Why this is better than placeholder:
- Users get a clear next step.
- PWA launch from Safari has a stable, non-blocking page.
- You avoid confusion when someone opens the app without a room URL.

---

## Do We Still Need `/launch/room/{slug}`?
Short answer: **No, not required** with Alternative 1.

Reason:
- If `/` is public, opening from Home Screen no longer triggers admin auth.
- Users can open shared `/room/{slug}` directly, enter room password, and continue.
- The main reason for `/launch/room/{slug}` was to avoid getting trapped behind admin gate at `/`.

So in Alternative 1:
- `/launch/room/{slug}` becomes optional compatibility route.
- You can keep it temporarily, then remove it after confirming Safari behavior is stable.

---

## Recommended Migration Strategy (Low Risk)

### Phase 1: Move admin gate
- Remove middleware protection from `/`.
- Protect `/admin` (and admin actions) with admin auth.

### Phase 2: Add public root page
- Build a small root page with guidance + admin link.
- Keep room routes unchanged.

### Phase 3: Keep `/launch/room` temporarily
- Keep existing `/launch/room/{slug}` for compatibility.
- Update sharing UX to recommend direct room link (`/room/{slug}`) first.

### Phase 4: Verify on iOS Safari
Test with a fresh install (delete old icon first):
1. Open shared room link in Safari.
2. Add to Home Screen.
3. Launch from icon.
4. Confirm: no admin password wall.
5. Confirm: room password flow still works.

### Phase 5: Decide cleanup
- If stable for 1-2 weeks, remove `/launch/room/{slug}` and related UI text.

---

## Security Notes
- This does **not** make rooms public without passwords.
- Room protection still comes from each room password.
- Only admin features move behind `/admin` auth.

Think of it like this:
- Room password = "friend access"
- Admin password = "owner management access"

Different jobs, different URLs.

---

## Architecture Impact Check
Current `ARCHITECTURE.md` says Python + NiceGUI + SQLite and room-based collaboration boundaries.
This alternative stays aligned with that architecture.

Only routing/auth boundaries change:
- Admin boundary moves from `/` to `/admin`.
- Room boundary remains room-password based.

No database redesign is required.

---

## Why This Is Usually Best for Your Case
Your real usage is:
- You send room links to friends.
- Friends should never see admin login.

Alternative 1 matches that directly and reduces Safari-specific edge cases.

---

## Progress Tracking
- [x] Explain what Alternative 1 changes.
- [x] Explain what root (`/`) should contain.
- [x] Explain whether `/launch/room` is still needed.
- [x] Provide phased migration plan with low-risk rollout.
