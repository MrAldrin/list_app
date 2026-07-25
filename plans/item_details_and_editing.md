# Item Details & Direct Editing Implementation Plan

## Goal
Improve the user experience for managing list items by allowing users to tap directly on an item's name to open a combined "Edit Item" modal (editing both Item Name and Description/Notes). Add a visual note icon indicator on the item row when a description exists. Simplify the item row by removing the edit pen button from edit mode.

---

## Technical Context & References
- Database schema: `src/database_setup.py` (`items` table definition).
- CRUD operations: `src/database_crud.py` (`get_list_data`, `rename_item`).
- Business logic: `src/item_service.py` (`rename_item_with_checks`).
- UI Rendering: `src/main.py` (`item_list` function).

---

## Proposed Changes

### 1. Database Schema & Migration
**Files:** `src/database_setup.py`, `src/database_crud.py` `[MODIFY]`

- Add `description TEXT DEFAULT ''` to `items` table schema in `database_setup.py`.
- Add automatic column migration check in `init_db()` (using `PRAGMA table_info(items)`) to ensure existing SQLite databases automatically receive the `description` column without breaking.
- Update `get_list_data(list_id)` query in `database_crud.py` to select `description` and return it in the item dictionaries (`id`, `name`, `description`, `done`, `active_tags`).
- Add `update_item_details(item_id, list_id, name, description)` function in `database_crud.py`.

---

### 2. Business Logic Layer
**File:** `src/item_service.py` `[MODIFY]`

- Create `update_item_details_with_checks(list_id, item_id, new_name, new_description)`:
  - Validates `new_name` (cannot be empty).
  - Checks for duplicate item names in the same list (ignoring the current item itself).
  - Calls `update_item_details` and returns status (`STATUS_ADDED`, `STATUS_INVALID_NAME`, or `STATUS_DUPLICATE_NAME`).

---

### 3. Frontend UI Updates
**File:** `src/main.py` `[MODIFY]`

- **Clickable Item Name & Indicator Icon:**
  - In `item_list(list_id, ...)`:
    - Update item row rendering:
      ```python
      # Make title label clickable with visual cue
      title_label = ui.label(item["name"]).classes(f"min-w-0 truncate cursor-pointer hover:text-primary {label_style}")
      title_label.on("click", lambda it=item: open_edit_dialog(it))
      
      # Show description icon indicator if item has notes
      if item.get("description"):
          ui.icon("description", size="16px").classes("text-slate-400 shrink-0").tooltip(item["description"])
      ```

- **Combined Edit Modal (`open_edit_dialog`):**
  - Displays a modal dialog with:
    - `ui.input(label="Item Name", value=it["name"])`
    - `ui.textarea(label="Description / Notes", value=it["description"])`
    - Save and Cancel buttons.
    - Delete button (optional quick action inside modal).
  - On Save: calls `update_item_details_with_checks(...)` and `broadcast_updates()`.

- **Edit Mode Cleanup:**
  - Remove the edit pen button (`ui.button(icon="edit")`) from `item_list` when `is_edit_mode` is active, since clicking the item name handles editing directly.
  - Retain edit mode for quick tags toggling and deletion (`icon="delete"`).

---

## Verification Plan

### Automated / Backend Tests
- Run existing database tests / verification scripts if present, or test DB column migration script.

### Manual Verification
1. **Tap Name to Edit:**
   - Launch app via `python src/main.py`.
   - Click on an item name $\rightarrow$ verify Edit Item dialog opens.
   - Update both name and description $\rightarrow$ verify both persist and update in real-time across connected browser tabs.
2. **Visual Indicator:**
   - Add a description to an item $\rightarrow$ verify note icon (`description`) appears next to item name.
   - Clear description $\rightarrow$ verify note icon disappears.
3. **Checkbox Independence:**
   - Click checkbox to check off item $\rightarrow$ verify modal does NOT open and item is checked off normally.
4. **Edit Mode Cleanup:**
   - Toggle Edit Mode ON $\rightarrow$ verify pen icon is gone, but tag circles and trash icon remain usable.

---

## Tracking & Progress
- [ ] Add `description` column migration to `src/database_setup.py` & `src/database_crud.py`
- [ ] Add `update_item_details_with_checks` in `src/item_service.py`
- [ ] Make item name clickable and add visual description indicator in `src/main.py`
- [ ] Implement combined Name + Description Edit Dialog in `src/main.py`
- [ ] Remove redundant pen icon from `is_edit_mode` in `src/main.py`
- [ ] Test end-to-end functionality in browser
