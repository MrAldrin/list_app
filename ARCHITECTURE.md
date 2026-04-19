# Architecture: Shared Shopping List App

## Purpose
This document defines the minimal architecture for the app.
It explains how the system should work, without locking down detailed implementation steps.

The app goal is a mobile-first shared list experience where small groups can add items, mark done items, and organize/filter the list.

This architecture optimizes for simplicity and learning speed over horizontal scaling.

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
- There should be a filter for showing checked off elements or not

## Core Architecture Decisions
- Frontend/Backend: Python with NiceGUI
- Data Storage: sqlite
- Published on railway free-tier with volume storage 

## How Real-Time Collaboration Works
- Clients connect to the NiceGUI server in the browser.
- When a user changes the list, the server persists the change and updates connected clients in the same room.
- Real-time sync is handled by the app server connection layer (WebSocket/push behavior), while SQLite is used for storage.

This means SQLite is valid for web sync in this architecture: storage and real-time updates are separate concerns.

## Data Boundaries (Evolvable)
The domain is intentionally small:
- `Room`: shared collaboration space.
- `Item`: list entry belonging to a room.
- `Category`: optional grouping label for items.

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
