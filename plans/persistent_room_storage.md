# Detailed Implementation Plan: Browser LocalStorage Room Persistence

## 1. Goal Overview
Eliminate room password fatigue across browser closes, app restarts, and Railway container redeploys. Room authorization will be saved directly to the user's browser `localStorage` (`listapp_room_{slug}` and `listapp_last_room`).

---

## 2. Architecture & Security Specs

- **Storage Keys:**
  - `listapp_room_{slug}`: Stores the room password or token for room `{slug}`.
  - `listapp_last_room`: Stores the slug of the last successfully visited room.
- **Validation Rule:**
  - Client-side stored keys are **always verified server-side** using `verify_room(slug, password)` from `database_crud.py`.
  - If a stored password is valid, `slug` is appended to `app.storage.user["authorized_rooms"]` and room access is granted.
  - If a stored password fails validation (e.g. password was changed), the invalid entry is cleared from `localStorage` via JS, and the inline password prompt is rendered.
- **Sharing Security Intact:**
  - Direct list access (`/list/{slug}`) remains public without revealing room passwords or granting room access.

---

## 3. Detailed File Modification Instructions

### File A: [src/main.py](file:///home/hsa/projects/list_app/src/main.py)

#### 1. Update `room_page(slug: str)` (around line 571)
- When `slug not in auth_rooms`:
  - Run an async JS client check before rendering the password form:
    ```python
    saved_pw = await ui.run_javascript(
        f"return localStorage.getItem('listapp_room_{slug}')",
        timeout=3.0
    )
    ```
  - If `saved_pw` is present and `verify_room(slug, saved_pw)` is `True`:
    - Add `slug` to `auth_rooms`.
    - Update `app.storage.user.update({"authorized_rooms": auth_rooms, "last_room_slug": slug})`.
    - Also ensure `localStorage.setItem('listapp_last_room', slug)` is kept fresh.
    - Render room content directly!
  - If `saved_pw` is invalid:
    - Run `ui.run_javascript(f"localStorage.removeItem('listapp_room_{slug}')")`.
    - Render the standard password input card.
- In the manual password submission handler:
  - When `verify_room(slug, pw_input.value)` succeeds:
    - Execute JS:
      ```python
      await ui.run_javascript(f"""
          localStorage.setItem('listapp_room_{slug}', {json.dumps(pw_input.value)});
          localStorage.setItem('listapp_last_room', {json.dumps(slug)});
      """)
      ```
    - Navigate to `/room/{slug}`.

#### 2. Update `index()` Router (around line 521)
- If `last_room_slug` is not in `app.storage.user`:
  - Check `localStorage`:
    ```python
    saved_last = await ui.run_javascript("return localStorage.getItem('listapp_last_room')", timeout=3.0)
    ```
  - If `saved_last` is found:
    - Check `saved_pw = await ui.run_javascript(f"return localStorage.getItem('listapp_room_{saved_last}')", timeout=3.0)`.
    - If `verify_room(saved_last, saved_pw)` is `True`:
      - Update `app.storage.user` with `authorized_rooms` and `last_room_slug`.
      - Navigate to `/room/{saved_last}`.

---

### File B: [ARCHITECTURE.md](file:///home/hsa/projects/list_app/ARCHITECTURE.md)
Update **Target Security Model** to explicitly record that:
- Rooms are protected by room passwords.
- Device authorization is persisted in browser `localStorage` (`listapp_room_{slug}` and `listapp_last_room`) to preserve room access across server restarts and browser closures.

---

### File C: [plans/plan_summaries.md](file:///home/hsa/projects/list_app/plans/plan_summaries.md)
Register `persistent_room_storage.md` as the active implementation plan for session & device persistence.

---

## 4. Verification Plan & Test Commands

### Automated Tests
Run pytest to verify no regressions in CRUD logic:
```bash
uv run pytest
```

### Manual Verification Scenarios
1. **Initial Login:** Open a room URL e.g. `http://localhost:8080/room/home-xxxx`, enter password. Verify room opens.
2. **Browser Close Test:** Close browser tab/window completely. Reopen `http://localhost:8080/room/home-xxxx` or `http://localhost:8080/`. Verify it opens instantly without asking for password.
3. **Server Restart Test:** Stop python process (`Ctrl+C`), restart `uv run python src/main.py`. Refresh browser. Verify access persists.
4. **Invalid Password Cleanup:** Manually set bad password in `localStorage`. Verify app cleans it up and presents password prompt cleanly.

---

## Progress Tracking
- [ ] Step 1: Implement `localStorage` auto-unlock in `room_page` in `src/main.py`
- [ ] Step 2: Implement `localStorage` auto-redirect in `index()` in `src/main.py`
- [ ] Step 3: Update `ARCHITECTURE.md` and `plans/plan_summaries.md`
- [ ] Step 4: Run `uv run pytest` automated test suite
- [ ] Step 5: Perform manual browser close & server restart verification
