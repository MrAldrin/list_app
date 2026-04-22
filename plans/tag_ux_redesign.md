# UX tweaks

## Goal
Improve ui with regards to edit mode

## New decisions (latest)
- Remove explicit `Enable/Disable Quick Tags` controls from the app UI.
- Quick tags should be implicit:
  - If at least one tag exists, quick tags behavior is active.
  - If no tags exist, quick tags behavior is inactive.
- This implicit pattern should be used consistently across the app, including main/list menus.
- Tag management is done in `Edit` mode (add/remove tags there).


## Current behaviour and problem with them
- the following two things seems redundant. could/should we merge them or remove the 3 dot menu as the second option achieves the same result. then we could also remove the options on the list menu itself
  - there is a 3 dot menu to turn on and off quick tags. 
  - removing all quick tags and going out of edit mode does the same


when deleting someting, there is an inline restore option:
  - This does not go away after 5 seconds
  - it should be a ui.notify like the others or something similar. maybe this snackbar/toast element you talk about

## Resolution of raised issues
- Redundant toggle paths:
  - Agreed: we remove the dots toggle and rely on implicit quick-tag activation from tag existence.
  - Result: one mental model only, less menu complexity.
- Undo feedback style:
  - Agreed: replace inline restore UI with transient notification/snackbar style.
  - Undo action should be shown in the same visual family as other notifications.

## Implementation plan update
1. Remove `Enable/Disable Quick Tags` actions from list-page dots menu.
2. Remove quick-tag toggle actions from main/list menus where they exist.
3. Define `quick_tags_active = len(list_tags) > 0` in UI rendering logic.
4. Use `quick_tags_active` everywhere instead of explicit toggle flags.
5. Keep tag add/remove only in `Edit` mode.
6. Replace inline undo container with notification-based undo feedback.
7. Ensure undo expires after 5 seconds and cannot be triggered after expiry.



## Consistency rule
- Prefer explicit mode controls (`Edit` / `Done`) and implicit feature activation from data presence (e.g., tags exist) instead of duplicate on/off toggles in menus.
