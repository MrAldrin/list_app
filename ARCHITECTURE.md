# Architecture: Shared Shopping List App


## Purpose
This document defines the minimal architecture for the app.
It explains how the system should work, without locking down detailed implementation steps.

The app goal is a mobile-first shared list experience where small groups can add items, mark done items, and organize/filter the list.

This architecture optimizes for simplicity and learning.


## App specifications for the end goal for this app:
- Used by up to 4 users at the same time
- The app update for all users when one user makes a change
- The app should focus on users on mobile phones
- The add field also acts as an update field. The user should get feedback when adding element.
    - When the user writes a new element:
        - if a new element: Add to list
        - if exists:
            - if unchecked: do nothing
            - if checked: unchek the element


## Core Architecture Decisions
- Frontend/Backend: Python with NiceGUI
- Data Storage: sqlite
- Host: Railway free-tier with volume storage 


## Data Boundaries & Security Rules
The domain is intentionally small:
- `Room`: A workspace containing multiple lists. Protected by a room-specific password.
- `List`: A collection of items. Can be shared publicly via a direct URL (`/list/{slug}`).
- `Item`: list entry belonging to a list.
- `Category`: optional grouping label for items.


### Target Security Model
- **Admin Root:** The root URL (`/admin`) is protected by a global app password. A nonblank `APP_PASSWORD` is required for both local and hosted startup; missing configuration stops the app before opening the database. There is no fallback password or authentication bypass.
- **Self-service creation:** An authenticated admin can generate reusable, unguessable invitation links at `/create-room/{token}`, valid for seven days, and revoke them early. Only token hashes and timestamps are stored in a separate `room_invitations` table. The server rechecks validity transactionally when creating a room. Expiry or revocation never changes existing room access. Loading the admin invitation list deletes invitation records seven days after expiry or revocation, whichever occurred first; no background scheduler is required. Creators choose a room password and use the existing sign-in flow; there are no individual owner/member accounts. Invitation management callbacks recheck admin authentication. No rate limiting or CAPTCHA is included at this scale.
- **Room URLs are private:** The `/room/{slug}` URL requires a valid room password or a token issued after checking that password, including for authenticated admins. Admin login and `?admin=true` never grant room access. After a password check, HTTPS browsers remember an opaque room access token in a persistent, host-only `__Host-` cookie (`Secure`, `HttpOnly`, `SameSite=Lax`, one-year lifetime, path `/`); only its hash is stored in SQLite with the room's authorization version. A separate cookie remembers the last signed-in/migrated room for root routing, never authorization. Cookie writes require an exact same-origin request, a custom header, and a valid token; Socket.IO handshakes are restricted to same-origin. The browser confirms cookie acceptance before removing the old `localStorage` token (`listapp_room_token_{slug}`). Existing tokens migrate when read. Local HTTP development and unavailable cookies retain the localStorage fallback. Tokens pass through JavaScript during issuance/migration, so HttpOnly reduces persistent exposure but is not a complete XSS defense. The server validates that token for every private room read and operation, not merely an `authorized_rooms` cache. Password changes increase the authorization version and revoke existing tokens. `listapp_last_room` and its cookie counterpart remain only routing conveniences, so room access survives server restarts and browser closures without storing passwords in browser storage. Unauthorized users are shown an inline password prompt.
- **List URLs are public-by-link:** The `/list/{slug}` URL is directly accessible to anyone with the link. They can edit items on that list.
- **Room controls are isolated:** If a user accesses a list via a public link and tries to navigate "back" to the room, they are hit with the inline room password prompt unless previously authorized. They cannot access room settings without the room password.

Only these boundaries are fixed right now. Field-level schema details are allowed to evolve as we learn.


## Project Structure
- src/: Source code
    - main.py: entrypoint to app and UI
    - database_setup.py: SQLite schema definition and initialization.
    - database_crud.py: Direct database Create, Read, Update, and Delete operations.
    - item_service.py: Business logic for managing list items and real-time updates.
    - room_invitations.py: Expiring creation invitations, separate from ongoing room access.
    - room_cookies.py: Secure remembered-access cookie bridge and same-origin socket policy.
    - ui/room_invitations.py: Admin invitation controls and public creation form.
- `docs/`: Technical documentation.
- `plans/`: Feature-specific implementation plans.


## UX Direction
- Mobile-first design is the default
- **Home-screen installation:** Room pages advertise a room-specific manifest whose `start_url` is `/room/{slug}`, without credentials or admin query parameters. All manifests retain the existing app identity (`id: "/"`) and origin-wide scope: this is one ListR app, not a separate installed app per room. Switching rooms does not deliberately retarget an existing icon. Other pages retain the root launch manifest and remembered-room recovery. Existing icons may not update; browser/device installation behavior requires real-device checks. The goal is to preserve sign-in when installing from an authenticated room where the browser copies cookies (documented by Apple starting with iOS/iPadOS 17.2). This is not guaranteed across browsers, existing icons, cookie restrictions, or expiration; an installation without a valid token still shows a password prompt. Cookie transfer and installation behavior require real-device verification; no ongoing synchronization between browser and installed-app storage is assumed.
- UI decisions should prioritize quick list editing during shopping.


## Evolution Rules
- This document is the architecture source of truth.
- If implementation differs from this architecture, either:
  1. Bring implementation back in line, or
  2. Update this document to record the new direction.
- Detailed implementation plans belong in `plans/`, not here.
