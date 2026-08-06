# Feature Plan: Preserve Typed Text on Input Field (Replace Dropdown Select with Input + Autocomplete Menu)

## Overview
Currently, the "Add or Search" item row uses NiceGUI's `ui.select` component. When a user starts typing (e.g. `"grapef"`) and clicks outside the text field without selecting an item or pressing Enter, `ui.select` clears the text box on blur because it treats typed input as temporary dropdown filter text.

This plan replaces `ui.select` with a standard text input (`ui.input`) paired with a floating suggestions menu (`ui.menu`), ensuring that:
1. Typed text is never lost when clicking away or scrolling.
2. Pressing Enter submits whatever is typed in the text box and clears the field.
3. Clicking a suggestion from the popup list submits the selected item and clears the field.

---

## Web Development Concepts
- **Form Input Persistence**: Using native/standard text inputs (`ui.input`) so user input state is retained during `blur` (unfocus) events.
- **Floating Autocomplete Popup**: Decoupling the input control from the suggestions list using a popup menu (`ui.menu`) bound to the input's change events.

---

## Proposed Changes

### `src/main.py`
- Modify `_render_add_item_row(list_id: int)`:
  - Replace `search_input = ui.select(...)` with `search_input = ui.input(label="Add or Search").classes("flex-grow")`.
  - Create a floating `ui.menu` attached to `search_input`.
  - On text change/input, filter item history for matches. If matches exist, update and open the menu; otherwise close the menu.
  - On suggestion click: set input value, execute `submit()`, close menu, and clear the input field.
  - On `keyup.enter`: execute `submit()`, close menu, and clear the input field.
  - On clicking away (blur): the menu hides, while `search_input.value` remains untouched.

---

## Verification Plan

### Automated Tests
- Run `uv run pytest` to ensure all item addition and database unit tests pass.

### Manual Verification
1. Open a list in the app.
2. Type `"grapef"` into the "Add or Search" box.
3. Click anywhere outside the text field. Verify that `"grapef"` is still present in the input box.
4. Press Enter. Verify that `"grapef"` is added to the list and the input box is cleared.
5. Type `"g"` again, click a suggestion from the popup menu, and verify the item is added and the field is cleared.

---

## Progress Tracking
- [ ] Implement `ui.input` + autocomplete popup menu in `_render_add_item_row` in `src/main.py`
- [ ] Run pytest suite to verify no regressions
- [ ] Manually verify input persistence on blur and submission via Enter / popup click
