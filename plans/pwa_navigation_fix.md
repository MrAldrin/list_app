# PWA Navigation & Standalone Mode Investigation

## Problem
After introducing room routes and passwords, iOS Safari Home Screen behavior became inconsistent:
- Sometimes launching from Home Screen opens `/` and asks for Admin password.
- Sometimes launching gives `404`.
- Earlier issue (Safari URL bar reappearing when entering `/list/...`) improved after adding root scope.

We need a Safari-reliable approach that avoids both admin redirect and `404`.

## Potential Causes

### 1. `start_url` ambiguity across iOS install flows
`start_url: "/"` is safe for availability, but always launches to admin-gated root.
`start_url: "."` can resolve unexpectedly relative to manifest path (`/static/...`) and cause `404`.

### 2. Manifest Location
Manifest is served from `/static/manifest.json`. Relative `start_url` values are risky when manifest is not at root.

### 3. Navigation between different root paths
The app uses:
- `/room/...`
- `/list/...`
These are sibling paths. Root `scope` is required to keep standalone mode when moving between them.

## Proposed Solutions

### Decision
Use a deterministic launch URL that always exists (`/`), and add an app-level redirect mechanism so room installs still open the correct room without asking for admin password.

### Step 1: Keep manifest root-safe
- `scope: "/"`
- `start_url: "/"`
- Keep manifest at `/static/manifest.json` (works as long as URL values are absolute)

This eliminates `404` from relative start URL resolution.

### Step 2: Add explicit room-launch shortcut
Introduce a stable room launch route, e.g.:
- `/launch/room/{slug}`

Behavior:
- If user is authorized for room in session: redirect to `/room/{slug}`.
- If not authorized: show room password prompt page and then continue to `/room/{slug}`.
- Never require admin password for this route.

Users add `/launch/room/{slug}` to Home Screen, not `/room/{slug}`.

Why this helps:
- PWA can still launch at `/` by manifest rules.
- Safari users who need room-specific install use a deterministic room-launch URL.
- No ambiguous relative URL handling.

### Step 3: Optional stronger fallback (if Safari still inconsistent)
Move list page to nested route:
- from `/list/{list_slug}`
- to `/room/{room_slug}/list/{list_slug}`

This keeps navigation within one path family and reduces Safari standalone exits.
Only do this if needed (higher migration cost).

### Step 4: UX guidance in-app
Add copy near room header/menu:
- "For iPhone Home Screen: save this `Launch Link`"
- Provide one-tap copy button for `/launch/room/{slug}`.

## Why it changed recently
Before multi-room, root and primary usage path were aligned. After route split and password gates, iOS manifest/install quirks became visible:
- root launch conflicts with room-only users
- relative launch can break when manifest lives under `/static`

## Implementation Notes (Simple Terms)
- Think of `manifest.start_url` as "where app icon opens first."
- Think of `scope` as "which URLs still look like app instead of browser."
- We keep `start_url` boring and safe (`/`), then build our own room entry path for people.
- This separates browser quirks from app security logic.

## Validation Checklist
1. Remove old Home Screen icons.
2. Install from Safari using room launch link.
3. Open app icon: should land in room flow, not admin login.
4. Enter a list: should remain standalone (no Safari URL bar controls).
5. Close app and reopen: should return to working flow without `404`.

## Progress Tracking
- [x] Diagnose two observed failures: admin redirect and `404`.
- [x] Define Safari-safe strategy (deterministic start URL + room launch route).
- [ ] Implement `/launch/room/{slug}` route and prompt/redirect behavior.
- [ ] Add "Copy Launch Link" UI for room owners/admin.
- [ ] Safari test pass on fresh Home Screen installs.
