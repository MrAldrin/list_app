# Item Quantities & Counter UI Implementation Plan

Add item quantity/counter support (e.g., "2x Tomatoes") to the list app, with side-by-side JJ workspace prototypes for **Option 1 (Inline Counters)** and **Option 2 (Modal Details Edit + Badge)**.

---

## Technical Approach & Architecture

### Foundation (Shared DB & Backend)
1. **Database Schema Update (`database_setup.py`)**:
   - Add `quantity INTEGER DEFAULT 1` column to the `items` table.
   - Run safe migration (`ALTER TABLE items ADD COLUMN quantity INTEGER DEFAULT 1;`) if column missing.
2. **Data Access (`database_crud.py`)**:
   - Update item fetch queries to include `quantity`.
   - Add `update_item_quantity(item_id, quantity)`.
3. **Business Logic (`item_service.py`)**:
   - Add `set_item_quantity(item_id, new_quantity)` and `adjust_item_quantity(item_id, delta)`.
   - Validate quantity $\ge 1$.

---

## Prototype Workspaces & UI Options

We will build the foundation on `dev`, then create two side-by-side Jujutsu (`jj`) workspaces on separate ports so the user can test both options on mobile simultaneously.

### Workspace A: `prototype-inline` (Port 8080) — Option 1
- **UI Design**: Inline `[-] 2 [+]` stepper buttons directly on each item row next to the checkbox.
- **List Setting Toggle**: Add a "Show Inline Counters" toggle in the list settings menu (top right) to turn inline counter buttons on/off per list.
- **Port & Execution**: `uv run src/main.py --port 8080`

### Workspace B: `prototype-modal` (Port 8081) — Option 2
- **UI Design**: Keep main list view clean. Items with quantity > 1 display a subtle badge (e.g. `2x Tomatoes`).
- **Modal Editing**: Tapping an item opens the Item Details modal, which contains a `[-] quantity [+]` input control.
- **Port & Execution**: `uv run src/main.py --port 8081`

---

## Proposed File Changes

### Foundation (Database & Services)

#### [MODIFY] [database_setup.py](file:///home/hsa/projects/list_app/src/database_setup.py)
- Update SQLite schema for `items` table to include `quantity INTEGER DEFAULT 1`.
- Add column check logic for existing databases.

#### [MODIFY] [database_crud.py](file:///home/hsa/projects/list_app/src/database_crud.py)
- Include `quantity` field in item tuples / dicts.
- Add `update_item_quantity(item_id: int, quantity: int)`.

#### [MODIFY] [item_service.py](file:///home/hsa/projects/list_app/src/item_service.py)
- Add `adjust_item_quantity(item_id: int, delta: int)` with non-negative check.

---

### UI Implementation (`src/main.py`)

#### Option 1 Workspace (`prototype-inline`)
#### [MODIFY] [main.py](file:///home/hsa/projects/list_app/src/main.py)
- Update item row rendering to include inline `-` button, quantity chip, `+` button.
- Wire button clicks to real-time `adjust_item_quantity` and websocket broadcasts.
- Add list-level toggle in top-right edit/settings dialog.

#### Option 2 Workspace (`prototype-modal`)
#### [MODIFY] [main.py](file:///home/hsa/projects/list_app/src/main.py)
- Update item row rendering to display `2x` quantity badge next to item text when `quantity > 1`.
- Update item details dialog to include a quantity counter control (`[-] count [+]`).

---

## Implementation Steps & JJ Feature Workflow

1. **Step 1 (Foundation - Baseline Commit)**:
   - Implement DB migration in `database_setup.py`, CRUD functions in `database_crud.py`, service logic in `item_service.py`.
   - Test backend quantity update logic.
   - Set bookmark: `jj bookmark set dev -r @`

2. **Step 2 (Workspace A - Option 1: Inline Counters)**:
   - Create workspace: `jj workspace add prototype-inline`
   - In `prototype-inline`, implement inline counter UI & list setting toggle.
   - Run server: `uv run src/main.py --port 8080`

3. **Step 3 (Workspace B - Option 2: Modal + Badge)**:
   - Create workspace: `jj workspace add prototype-modal`
   - In `prototype-modal`, implement quantity badge & item details modal counter.
   - Run server: `uv run src/main.py --port 8081`

---

## Verification Plan

### Automated Tests
- Test database CRUD quantity updates and boundary constraints (quantity $\ge 1$).

### Manual Verification
- Launch both servers on separate ports (`8080` and `8081`).
- Open both URLs on mobile / browser.
- Verify real-time updates when counter is incremented/decremented.
- Verify toggle setting in Option 1 list settings.

---

## Progress Tracking
- [ ] Database Schema & CRUD quantity field
- [ ] Item Service quantity update logic
- [ ] JJ Workspace `prototype-inline` (Option 1 on Port 8080)
- [ ] JJ Workspace `prototype-modal` (Option 2 on Port 8081)
- [ ] Verification & side-by-side comparison
