# Browser test port map: NiceGUI to Svelte

Supporting detail for [real-browser tests](../browser-testing.md) and step 3.7
of the [Svelte rewrite plan](../../plans/svelte-frontend-rewrite.md). Each
NiceGUI browser test is mapped to its Svelte version. Step 4.3 deleted the
NiceGUI tests ([retirement list](nicegui-test-retirement.md)).

Status:

- **Ported:** a new Svelte test made in step 3.7.
- **Covered:** a Svelte test from an earlier step already checks it.
- **Not applicable:** NiceGUI internals; the reason is given.

## Mapping

| NiceGUI test | Status | Svelte test |
|---|---|---|
| `test_deleted_lists.py::test_stale_page_rejects_actions_after_list_deletion` (6 actions) | Ported | `test_svelte_deleted_lists.py::test_stale_page_cannot_write_after_list_deletion` (same 6 actions, same role per engine) |
| `test_deleted_lists.py::test_stale_page_after_room_deletion_has_no_room_navigation` | Ported | `test_svelte_deleted_lists.py::test_stale_page_after_room_deletion_has_no_room_navigation` |
| `test_public_sharing.py::test_sharing_live_updates_revocation_and_restart`: live updates both ways, reset, new link | Covered | `test_svelte_share.py::test_visitor_views_and_edits_by_link_and_reset_stops_it` |
| … the room's list address refused to a visitor | Ported | `test_svelte_share.py::test_visitor_edits_tags_but_cannot_rename_or_delete_the_list` |
| … an edit saved from a dialog left open during the reset | Ported | `test_svelte_share.py::test_edits_and_tags_sent_after_a_reset_change_nothing` |
| … remembered room and share link after a restart | Ported | `test_svelte_restart.py::test_remembered_room_and_share_link_survive_a_restart` |
| … the Service Worker is active before and after the restart | Not applicable | NiceGUI's own service worker. Svelte has none until step 5.1, which brings its own tests (5.5). |
| `test_public_sharing.py::test_open_room_tab_recovers_after_server_restart` | Ported | `test_svelte_restart.py::test_open_list_page_recovers_after_a_restart`. NiceGUI reloads the page; the Svelte test checks the opposite: no reload, the live stream reconnects. |
| `test_public_sharing.py::test_reset_cancels_public_undo_but_keeps_room_access` | Covered | `test_svelte_share.py::test_writes_sent_after_a_reset_change_nothing` |
| `test_public_sharing.py::test_revoked_tab_cannot_add_and_existing_room_tab_keeps_access` | Covered | `test_svelte_share.py::test_writes_sent_after_a_reset_change_nothing` |
| `test_public_sharing.py::test_public_visitor_edits_tags_but_cannot_rename_list` | Ported | `test_svelte_share.py::test_visitor_edits_tags_but_cannot_rename_or_delete_the_list` (adding a tag was already covered) |
| `test_public_sharing.py::test_revoked_room_tab_cannot_save_open_rename_dialog` | Ported | `test_svelte_live.py::test_rename_saved_after_a_password_change_changes_nothing` |
| `test_public_sharing.py::test_revoked_public_tab_cannot_save_tag` | Ported | `test_svelte_share.py::test_edits_and_tags_sent_after_a_reset_change_nothing` |
| `test_public_sharing.py::test_cancel_reset_keeps_public_link_working` | Covered | `test_svelte_share.py::test_visitor_views_and_edits_by_link_and_reset_stops_it` |
| `test_public_sharing.py::test_invalid_tokens_never_render_list_contents` | Covered | `test_svelte_share.py::test_invalid_links_show_no_list` |
| `test_visibility_settings.py::test_visibility_settings_modes_history_and_shared_updates` | Ported | `test_svelte_hide_done.py::test_hide_done_modes_history_and_shared_updates` ("All" alone was in `test_svelte_items.py`) |
| `test_theme.py::test_theme_is_remembered_per_browser` | Covered | `test_svelte_theme.py` (other browsers keep their choice; shared with NiceGUI) |
| `test_theme.py::test_saved_theme_paints_before_nicegui_scripts` | Covered | `test_svelte_theme.py::test_saved_theme_paints_before_the_app_scripts` |

New, with no NiceGUI test: `test_svelte_toasts.py` checks that toasts are
small and inside the screen (Gate A).

## How the stale-action tests differ

- **Holding back updates.** NiceGUI tests delay Socket.IO frames. The Svelte
  tests make the page's live stream (`…/events`) never connect, so the page
  misses the delete, reset or password change, like a phone that was asleep.
- **Proof the action was sent.** NiceGUI tests match the outgoing Socket.IO
  event to the clicked control. The Svelte tests wait for the `…/ops`
  answer: `rejected` for a room page, 401 for a share page or a revoked room.
- **Undo timing.** The other phone opens its delete dialog first, so the stale
  Undo is sent within its 5 s.

## Toast layout check

Each toast must be at most 48 px high and inside the screen, also with a long
message, three stacked toasts, an open dialog and a short landscape screen.
The toast area may be no taller than its toasts. Over an open dialog the test
compares a screenshot pixel with the toast color: a modal dialog makes the
rest of the page inert, so the browser's hit test never finds the toast.
