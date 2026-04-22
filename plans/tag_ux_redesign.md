# Tag UX tweaks

## Goal
Define intuitive and easy-to-use UI for quick tags.

## Assumptions
- We use one shared app-level `Edit mode` pattern (not tag-only), and this pattern can be reused in other screens/features.
- In normal mode, destructive actions are hidden where practical to reduce accidental taps.
- In edit mode, destructive actions are visible and easy to access.
- The selected delete safety behavior is Option A: instant delete + snackbar/toast with `Undo` for 5 seconds.
- `Undo` should restore the deleted entity with its previous data (for tags: same label; for list items: same text, checked state, and connected tags).
- If no `Undo` is pressed before timeout, deletion is committed permanently.
- On mobile and desktop, the interaction model should be functionally the same (no requirement for long-press/right-click in MVP).
- Tag order should be alphabetical (not manual reordering).
- Edit mode stays active until the user presses `Done` (does not auto-close after a single change).
- Current in-scope UI behavior from your notes:
  - Normal mode:
    - show add/edit list input field
    - show tag toggle/filter area (tap tags to filter on/off)
    - list elements show checkbox, text, and tags
    - hide edit/delete controls on list elements
  - Edit mode:
    - show add/edit list input field
    - show add tags field
    - show delete controls in tag area
    - list elements show checkbox, text, tags, plus edit and delete controls
- Tag tap behavior in normal mode remains quick filtering behavior (same principle as today).
- This document defines UX direction only; implementation details in `src/main.py` can be phased.

## Current behaviour
Quick tags now have a small x next to them to remove them.

Problems:
- These tags are not removed often, so a permanent delete button creates visual noise.
- The delete button can be clicked by mistake.


## UX recommendation for MVP
Use a safer but discoverable pattern:
- Default view (normal mode): hide destructive controls.
- Show destructive actions only when user enters explicit `Edit mode`.
- In edit mode, show small `x` buttons on tags and edit/delete controls on list items.
- When deleting, use undo feedback (Option A) instead of confirmation dialog.

Why this is good for first version:
- Prevents accidental deletion in normal use.
- Keeps UI clean.
- Keeps delete discoverable and simple to implement.
- Works consistently on both mobile and desktop.

## Screen states (baked from comments)
Normal mode:
- show add/edit list input field
- show tag toggle area for filter on/off
- list elements show checkbox, text, and tags
- hide tag delete controls
- hide list-item edit/delete controls

Edit mode:
- show add/edit list input field
- show add tags field
- show tag delete controls
- list elements show checkbox, text, tags, plus edit and delete controls
- edit mode remains active until user presses `Done`

## Suggested interaction model
Primary action (always visible):
- Tap/click tag = apply/use tag quickly.

Secondary actions (less frequent):
- `Edit mode` button in top area opens management mode.
- In management mode:
  - `+ Add tag`
  - delete controls on each tag
  - edit/delete controls on each list item
  - `Done` exits management mode

## Safety options for deletion
- Option A (selected): Instant delete + snackbar/toast with `Undo` for 5 seconds.


## Simple implementation phases
1. Introduce shared app-level `Edit mode` toggle.
2. Hide destructive controls in normal mode (tags and list items).
3. Reveal destructive controls in edit mode.
4. Add undo snackbar for delete actions (5-second window).

## Implementation checklist
- [x] Add `edit_mode` state on list page and a header toggle button (`Edit` / `Done`).
- [x] In normal mode, hide list-item edit/delete controls.
- [x] In edit mode, show list-item edit/delete controls.
- [x] In normal mode, keep tag filter buttons visible.
- [x] In normal mode, hide tag add field and tag delete controls.
- [x] In edit mode, show tag add field and tag delete controls.
- [x] Add 5-second undo flow for item deletion.
- [x] Add 5-second undo flow for tag deletion.
- [x] Refresh tag/item UI after each mode switch and undo/delete action.
- [ ] Manually verify both modes on desktop and mobile-sized layout.

## Decisions
- Tags are shown alphabetically (no manual reorder).
- Edit mode stays open until `Done`.
- Long-press/right-click interactions are out of MVP scope.
- Delete safety is undo-based (Option A), not confirmation-dialog based.

## Progress tracking
- [x] Problem clarified
- [x] Feasibility of long-press/right-click answered
- [x] MVP UX direction proposed
- [x] Final UX decisions written into plan
- [x] Implementation started in `src/main.py`
