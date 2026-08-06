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
- **Admin Root:** The root URL (`/admin`) is protected by a global app password.
- **Room URLs are private:** The `/room/{slug}` URL always requires a valid room password. Device authorization is persisted in browser `localStorage` (`listapp_room_{slug}` and `listapp_last_room`) to preserve room access across server restarts and browser closures while always validating credentials server-side. Unauthorized users are shown an inline password prompt.
- **List URLs are public-by-link:** The `/list/{slug}` URL is directly accessible to anyone with the link. They can edit items on that list.
- **Room controls are isolated:** If a user accesses a list via a public link and tries to navigate "back" to the room, they are hit with the inline room password prompt unless previously authorized. They cannot access room settings without the room password.

Only these boundaries are fixed right now. Field-level schema details are allowed to evolve as we learn.


## Project Structure
- src/: Source code
    - main.py: entrypoint to app and UI
    - database_setup.py: SQLite schema definition and initialization.
    - database_crud.py: Direct database Create, Read, Update, and Delete operations.
    - item_service.py: Business logic for managing list items and real-time updates.
- `docs/`: Technical documentation.
- `plans/`: Feature-specific implementation plans.


## UX Direction
- Mobile-first design is the default
- UI decisions should prioritize quick list editing during shopping.


## Evolution Rules
- This document is the architecture source of truth.
- If implementation differs from this architecture, either:
  1. Bring implementation back in line, or
  2. Update this document to record the new direction.
- Detailed implementation plans belong in `plans/`, not here.
