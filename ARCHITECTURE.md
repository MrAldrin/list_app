# Architecture: Shared Shopping List App

## Purpose
This document defines the minimal architecture for the app.
It explains how the system should work, without locking down detailed implementation steps.

The app goal is a mobile-first shared list experience where small groups can add items, mark done items, and organize/filter the list.

## Core Architecture Decisions
- `NiceGUI` is used as the web framework, so frontend and backend live in one Python app.
- `SQLite` is the initial database for persistent storage.
- The system runs as one web server process for MVP usage.
- Collaboration uses shared room codes with no login in v1.

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
- `src/`: Core Python application code.
  - `main.py`: Entry point and UI definitions.
  - `models.py`: SQLite database schema (planned).
  - `database.py`: DB connections (planned).
- `docs/`: Technical documentation.
- `plans/`: Feature-specific implementation plans.

## UX Direction
- Mobile-first design is the default (iPhone-sized viewport first).
- Desktop support is secondary.
- UI decisions should prioritize quick list editing during shopping.

## Scale and Constraints
- Target scale: up to 4 concurrent users.
- Target behavior: near real-time updates for users in the same room.
- This architecture optimizes for simplicity and learning speed over horizontal scaling.

## Evolution Rules
- This document is the architecture source of truth.
- If implementation differs from this architecture, either:
  1. Bring implementation back in line, or
  2. Update this document to record the new direction.
- Detailed implementation plans belong in `plans/`, not here.
