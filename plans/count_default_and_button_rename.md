# Feature Plan: Quantity Count Default OFF, Rename "Edit" Button, and "Only > 1" Sub-Option

## Overview
1. Turn quantity count display off by default when opening a list.
2. Rename header button "Edit" to "Options".
3. Add sub-option under "Show quantities" to only display counters for items with quantity > 1.

## Web Development Concepts
- **View State Defaults**: Initializing state variables (`show_counters: False`, `only_gt_1: False`) in page components.
- **Dependent Controls**: Conditionally rendering sub-toggles only when their parent feature is enabled.

## Proposed Changes
- `src/main.py`: Update `ViewState`, `item_list`, `_create_tags_ui`, and `list_page`.

---

## Progress Tracking
- [x] User feedback on button name selection ("Options")
- [x] Implement initial quantity default off and "Options" rename
- [x] Add "Only show if count > 1" sub-option toggle in `src/main.py`
- [x] Verify unit tests (`uv run pytest`)
- [x] Verify UI behavior
