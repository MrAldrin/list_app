# PWA & iOS Safari Navigation Quirks

This document serves as a reference for why the application's root routing (`/`) and admin paths (`/admin`) are structured the way they are. This is specifically to solve erratic behavior caused by Progressive Web App (PWA) standalone modes on iOS Safari.

## The Original Problem
Initially, the `start_url` for our PWA manifest was `/`, and `/` was protected by the global Admin Password. 

When a standard user (who only had access to a specific room, e.g., `/room/family`) saved the app to their iPhone Home Screen, the app icon would always launch the `start_url` (`/`). This forced the user to face the Admin Login wall, completely breaking the illusion that the room was their own private app.

Additionally, navigating between sibling paths (`/room/` and `/list/`) sometimes caused Safari to exit "standalone mode" (bringing back the browser URL bar) or throw 404 errors if relative manifest paths weren't handled perfectly.

## The Solution

To create a Safari-reliable approach, we split the responsibilities of the URLs:

1. **Deterministic Start URL (`/`)**: 
   The manifest `start_url` is kept boring and safe at `/`. 
   However, we changed the logic at the root. It is **no longer the admin panel**. Instead, it acts as a smart router. It checks local storage (`app.storage.user`) to see if the user was recently in a specific room. If they were, it silently redirects them straight to `/room/{slug}`. 

2. **Isolated Admin Panel (`/admin`)**:
   The admin tools and the global password gate were moved to a dedicated `/admin` and `/admin/login` route. Normal users never see this URL.

3. **Room-Scoped Navigation**:
   To keep Safari in "standalone mode" (hiding the URL bar), the manifest `scope` is kept at `/`. This ensures that when users navigate from a list back to a room, Safari recognizes they are still within the same application.

## Summary for Future Debugging
If users report that launching the app from their home screen asks them for an Admin password, it means the `auth_middleware` in `main.py` is overly aggressive and is catching the root `/` route. 
The root `/` must remain a public, open router so PWA users can smoothly be redirected to their specific rooms.