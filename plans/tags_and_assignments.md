# Plan: Optional List-Level Tags / Assignments

## 1. Overview
The goal is to allow users to optionally enable a tagging system for specific lists to quickly assign tasks or categorize them.

Crucially, this entire feature is **opt-in per list**. By default, lists will look and function exactly as they do now (simple text items). Users can turn this feature on or off for a specific list from the **home page** (list settings/selection page).

When enabled, these are **"per-list" tags**: the available tags are defined on the list itself. Once a tag is added to the list, every item in that list will display a small toggle button for it (showing just its first letter). Users can tap to toggle assignments on or off directly on the row. An item can have multiple active tags.

This design is optimized for a small, fixed set of tags (like "Me", "Partner", "Urgent") and extremely fast mobile assignment.

## 2. Data Model Architecture
We will stick to SQLite and keep it simple without creating complex relational tables.

1. **Lists Table Update**: 
   - Add an `enable_tags` column (BOOLEAN, default `FALSE`).
   - Add a `list_tags` column to store the available tags (e.g., as a JSON array of strings `["Me", "Partner"]`). Colors will be assigned based on their index to keep the schema simple.
2. **Items Table Update**:
   - Add an `active_tags` column to store the currently *toggled on* tags for that specific item (e.g., as a JSON array `["Me"]` or comma-separated string `"Me,Partner"`).

## 3. UX and UI Direction (Mobile-First)

### Home Page (List Settings)
- On the home page where users view/select their lists, add a toggle or setting for each list: "Enable Quick Tags".
- If this is off, the list UI is completely unchanged from its current state.

### List UI (When feature is Enabled)
#### Layout Order (Top to Bottom)
1. **Add Item Area:** The main input field and "Add" button for creating new list items.
2. **Add List Tag Area:** Right below the item input, an area to add new tags to the *list itself*.
3. **List Tags Display / Filter Row:** Below the tag creation area, display all the `list_tags` currently defined for this list. 
   - They will be displayed with their **full names** and **different colors** (e.g., colored pills/chips).
   - Tapping these pills acts as the **filter**: tapping "Me" hides all items that don't have "Me" active.
4. **The List Items:** The main list of tasks.

#### The Item Row (Assigning)
- On *every* item row, we will render a small, circular button for *every* tag defined in the List's `list_tags`.
- The button will display only the **first letter** of the tag (e.g., "Me" -> **M**, "Partner" -> **P**) to save space.
- The button will use the tag's assigned color.
- **Inactive state:** The button has a subtle, faded background or outline.
- **Active state:** When tapped, the button becomes visually distinct (solid color) indicating the tag/assignee is active for that item.

## 4. Implementation Steps
1. **Database Schema:** 
   - Update `database_setup.py` to add `enable_tags` and `list_tags` to `lists`, and `active_tags` to `items`.
   - Update `database_crud.py` to handle reading/writing these new columns.
2. **Home Page UI:** 
   - Add a toggle for "Enable Quick Tags" when creating or managing a list on the home page.
3. **List Tags UI (List View):** 
   - *Only if `enable_tags` is True:*
     - Add a UI section below the main input to add new tags to the `List`.
     - Render the defined `List` tags as full-name, colored pills below the input area.
4. **Item Row UI:** 
   - *Only if `enable_tags` is True:*
     - Update the NiceGUI layout for an item. Loop through the list's `list_tags` and render a small toggle button (first letter, colored) next to the item name.
5. **Item Logic:** Wire up the row buttons to update the `items`'s `active_tags` in the database and trigger real-time updates.
6. **Filter Logic:** Wire up the full-name tag pills at the top to filter the displayed list items based on their `active_tags`.

---
## Progress Tracking
- [ ] Database schema updated (`lists.enable_tags`, `lists.list_tags`, `items.active_tags`)
- [ ] Home page UI updated with a toggle to enable/disable tags per list
- [ ] UI to add new tags to the List (conditionally rendered)
- [ ] UI to display full-name, colored tag pills as filters (conditionally rendered)
- [ ] UI updated to show first-letter tag toggle buttons on every item row (conditionally rendered)
- [ ] Item row buttons correctly update the database when toggled
- [ ] Filtering logic implemented to hide/show items when top pills are clicked