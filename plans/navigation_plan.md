# Navigation Plan: Start Page and List Management

## Goal
Improve the user experience by introducing a dedicated start page for list management. This will make the application feel more organized and keep the individual shopping lists focused on adding and checking items.

## Current State
- The app has a single page (`/`) that uses a dropdown selector to switch between lists.
- List creation, renaming, and deletion are also performed on this main page through buttons and dialogs next to the selector.

## Proposed Changes

### 1. Navigation Flow
- **Start Page (`/`)**: 
    - A hub for all available lists.
    - Each list entry has "Enter", "Edit" (Rename), and "Delete" actions.
    - A prominent "Create New List" button.
- **List Item View (`/list/{list_id}`)**:
    - Focused view of the selected list's items.
    - Add/Search items input.
    - Toggle "Done" status.
    - Rename/Delete individual items.
    - A "Back to Lists" button to return to the Start Page.

### 2. UI Design (Mobile-First)

#### Start Page (`/`)
- Header: "Våre lister" (Our lists).
- List Section: A vertical stack of cards or list items.
    - Each row contains:
        - List Name (Clickable or has an "Enter" button).
        - Icon buttons for Rename and Delete.
- Footer/Float: "Create New List" button.

#### List Item View (`/list/{list_id}`)
- Header: `<List Name>` with a back arrow icon to `/`.
- Existing item management controls (Input field, Filter, Item rows).
- "Hide Completed" switch.

### 3. Technical Implementation Details

#### Routing (NiceGUI)
- Update `src/main.py` to use multiple page decorators:
    - `@ui.page('/')` for the Start Page.
    - `@ui.page('/list/{list_id}')` for the item-specific view.
- Use `ui.navigate.to('/')` and `ui.navigate.to(f'/list/{list_id}')` for transitions.

#### State Management
- `list_id` will be passed via the URL, making it naturally "per-tab" and bookmarkable.
- Remove the existing `ACTIVE_LIST_STORAGE_KEY` and associated client storage logic if possible, as the URL becomes the source of truth for the active list.

#### Real-Time Updates
- `broadcast_updates()` should continue to refresh all clients. 
- Since NiceGUI's `@ui.refreshable` is page-local, we need to ensure that when a change happens in one list, other clients viewing *the same* list are updated.
- *Wait:* In NiceGUI, `@ui.refreshable` functions are indeed page-local. If we use multiple pages, we might need a more global way to trigger refreshes across clients. Actually, `ui.refreshable` can be triggered from outside if we keep references, but better is to use `ui.run_with(app, ...)` and potentially `app.on_connect` if we need more complex sync. 
- For now, let's stick to the simplest approach: `ui.refreshable` within each page, and a global broadcast that triggers `refresh()` on the relevant instances.

### 4. Step-by-Step Implementation

1. **Step 1: Create the Start Page (`/`)**
    - Implement a new `index()` function that lists all lists.
    - Add "Rename" and "Delete" dialogs (refactored from the current code).
    - Add "Create New List" dialog.
    - Link each list to `/list/{id}`.

2. **Step 2: Create the List View (`/list/{list_id}`)**
    - Implement a new `list_view(list_id: int)` function.
    - Move existing item-listing logic (`item_list`, `add_to_list`, `submit_item`) into this view.
    - Add a "Back" button to return to `/`.

3. **Step 3: Refactor shared logic**
    - Ensure dialogs and notifications are reused or properly placed.
    - Clean up `src/main.py` to reflect the new structure.

4. **Step 4: Verification**
    - Test navigation between pages.
    - Test list management on the start page.
    - Test item management within a list.
    - Test real-time sync (open two tabs on the same list).

## Progress
- [x] Step 1: Create Start Page
- [x] Step 2: Create List View
- [x] Step 3: Refactor and Clean up
- [ ] Step 4: Verification
