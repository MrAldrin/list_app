# NiceGUI test retirement (step 4.3)

Supporting detail for the [Svelte rewrite plan](../../plans/svelte-frontend-rewrite.md)
(decision 162). Step 4.3 removed NiceGUI, so the tests that drove its pages
were deleted. Before each deletion, the business rules it checked were looked up
in the API and unit tests; the few that were only checked through the NiceGUI
pages were ported. Counts are collected pytest items (parametrized cases
count each), measured before and after.

## Python tests deleted (13 files, 92 tests)

| File | Tests | What it checked | Business rules now covered by |
|---|---|---|---|
| `test_invitation_ui.py` | 8 | Invitation form, admin controls | `test_api_invitations.py` (create from link, reuse, recheck after hashing, revoke, admin only), `test_room_invitations.py` (expiry, revocation), `browser_tests/test_svelte_invitations.py` |
| `test_list_tag_ui.py` | 2 | Stale tag add and delete callbacks | `test_api_tag_ops.py` (tag add and remove merge with stored tags), `test_item_undo.py` (tag add keeps an earlier add), `test_tags.py` |
| `test_install_help.py` | 2 | Install help dialog | `browser_tests/test_svelte_install.py` |
| `test_live_refresh.py` | 2 | NiceGUI refresh with a deleted client | `test_api_events.py` (streams wake on every write) |
| `test_visibility_settings_ui.py` | 7 | Hide-done switches and counters | `test_item_visibility.py` (modes, bounds, atomic update, history), `test_api_tag_ops.py` (`list.visibility`), `browser_tests/test_svelte_hide_done.py`, `frontend/src/lib/list/hide-done.test.ts` |
| `test_theme_lifecycle.py` | 8 | Dark mode setup in NiceGUI | `browser_tests/test_svelte_theme.py`, `frontend/src/lib/ui/theme.test.ts` |
| `test_room_routing.py` | 16 | Pasted room links, remembered room | `frontend/src/lib/room-link.ts` tests, `browser_tests/test_svelte_rooms.py`, `test_svelte_old_urls.py` |
| `test_room_installation.py` | 6 | Install manifests, manifest links in `<head>` | `test_pwa_routes.py`, `test_svelte_install.py`. One rule changed: an unknown or deleted room's `.json` manifest now answers 200 like the `.webmanifest` one (no database lookup, decision 160) |
| `test_sharing.py` | 15 | Share button and copy fallback | `browser_tests/test_svelte_share.py`, `frontend/src/lib/ui/share.test.ts` |
| `test_list_deletion.py` | 7 | Deleted-list page state, refresh | `test_list_identity.py` (stale writes refused), `test_api_list_ops.py`, `browser_tests/test_svelte_deleted_lists.py` |
| `test_admin_rooms.py` | 6 | Admin page refresh and stale reset dialog | `test_api_admin.py` (overview, reset of a gone room, admin required), `test_database_crud.py` and `test_room_token_validation.py` (reset with a stale room identity), `browser_tests/test_svelte_admin.py` |
| `test_admin_room_authorization.py` | 10 | Admin and `?admin=true` never open a private room | Ported: `test_room_token_validation.py` (missing, invalid, valid, revoked, other-room tokens); `test_api_admin.py::test_admin_has_no_room_access` |
| `test_room_access.py` | 3 | `RoomAccess` class (module deleted, API has its own checks) | Ported: `test_room_token_validation.py` (password reset revokes, deleted room, database failure is 503 in `test_api_session.py`) |

## Python tests trimmed or rewritten

| File | Tests before, after | Change |
|---|---|---|
| `test_list_names.py` | 8, 7 | Dropped the Quasar button-caps test; all name rules stay |
| `test_public_share_tokens.py` | 19, 13 | Dropped the two NiceGUI page tests (reset dialog recheck, route visibility); token rules stay, reset rules are in `test_api_share.py` |
| `test_item_undo.py` | 4, 4 | Rewritten against `restore_deleted_item` and `add_list_tag` (no `main`) |
| `test_list_identity.py` | 62, 62 | Last test calls the database functions, not NiceGUI's undo helper |
| `test_room_cookies.py` | 15, 9 | The `/_room-access/{slug}` endpoint is gone (decision 160). Now: cookie names and the same-origin rule |
| `test_pwa_routes.py` | 4, 12 | Kill switch, old manifests, icons, favicon |
| `test_svelte_install.py` | 6, 4 | Uses `register_pwa_routes`; icons moved to `test_pwa_routes.py` |
| `test_svelte_frontend_routes.py` | 57, 58 | Cache headers per address; whole-app tests; no NiceGUI route tests |
| `test_api_session.py` | 28, 26 | Two tests of NiceGUI's cookie endpoint removed |
| `test_api_list_ops.py` | 57, 53 | Four NiceGUI refresh tests removed; startup prune tests use the lifespan |
| `test_api_basics.py`, `test_api_events.py` | same | NiceGUI handler checks and `broadcast_updates` replaced by `wake_streams` and the real app's handlers |
| `test_server_shutdown.py` | 1, 1 | Starts the plain uvicorn server |
| New: `test_room_token_validation.py` | 0, 10 | See above |

## Browser tests

| Retired | Browser tests (3 engines) | Svelte coverage |
|---|---|---|
| `test_deleted_lists.py` | 24 | `test_svelte_deleted_lists.py` |
| `test_public_sharing.py` | 27 | `test_svelte_share.py`, `test_svelte_restart.py` |
| `test_theme.py` | 9 | `test_svelte_theme.py` |
| `test_visibility_settings.py` | 3 | `test_svelte_hide_done.py` |
| `test_svelte_live.py::test_nicegui_and_svelte_see_each_others_changes` | 3 | none needed (one UI) |
| `test_svelte_theme.py::test_choice_is_shared_with_nicegui` | 3 | none needed |
| `test_svelte_admin.py::test_nicegui_admin_sign_in_does_not_carry_over_and_never_opens_a_room` | 3 | `test_svelte_old_urls.py` (`/admin/login`), `test_svelte_admin.py` |
| `test_svelte_invitations.py::test_a_svelte_invitation_works_in_nicegui` | 3 | none needed |

The full mapping from NiceGUI to Svelte browser tests is in the
[port map](browser-test-port-map.md). `test_svelte_live.py::test_password_change_revokes_open_pages`
changed the password through a second Svelte page instead of NiceGUI.
New: `browser_tests/test_old_service_worker.py` (3).
