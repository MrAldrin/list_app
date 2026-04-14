# MVP v1 Implementation Plan

This file contains implementation planning details that are intentionally separate from `ARCHITECTURE.md`.

## Reference starter
Use the official NiceGUI todo example as the guiding starting point:
- https://github.com/zauberzeug/nicegui/blob/main/examples/todo_list/main.py

How we use it:
- Reuse the interaction style and UI refresh patterns as a learning baseline.
- Keep its simplicity for the first iteration.
- Adapt it to our architecture needs (room-based shared lists + SQLite persistence + multi-user sync).

What we do not do:
- We do not copy the example 1:1.
- We do not keep in-memory-only state for final v1 behavior.

## Goal for v1
Deliver a working shared shopping list for small groups (up to 4 concurrent users), optimized for mobile use.

## Functional scope
- Create or join a room by short code
- Add list items
- Mark item complete/incomplete
- Assign category to item
- Filter by category
- Hide/show completed items

## Suggested delivery order
1. App shell and routing
- Start NiceGUI app with a simple room entry page
- Add create/join room flow

2. Persistence layer
- Add SQLite setup
- Add tables/entities for room, item, category
- Add basic CRUD helpers

3. Core list actions
- Add item creation
- Add item completion toggle
- Add item/category linking

4. Filtering behavior
- Add category filter
- Add hide-completed toggle

5. Real-time sync in room
- Broadcast list updates to connected clients in same room
- Refresh relevant UI sections after updates

6. Mobile polish
- Improve spacing, tap targets, and layout for phone viewport

7. Example-to-app alignment check
- Verify that patterns borrowed from the todo example still match `ARCHITECTURE.md`
- If they do not match, follow architecture and update plan details accordingly

## Data model draft (can evolve)
- Room: id, code, name, created_at
- Category: id, room_id, name
- Item: id, room_id, category_id, text, is_completed, created_at, updated_at

## Validation checklist
- Two browser sessions in same room receive updates quickly
- Checked/unchecked state syncs correctly
- Category filtering works
- Hide completed works with mixed item states
- Basic usability on iPhone-sized viewport

## Deployment notes (later)
- Keep local development first
- Evaluate free hosting option after MVP is stable
- Candidate: Render free web service
