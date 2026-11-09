## Review
Read-only cost/value review for lr-gt2 / lr-gt2.1. No files edited. No pytest. No children.

Facts kept:
- One full-suite sample after toast-dismiss helper: **486 passed, 120 skipped, 0 failed, 557.65s**. Archived final: **622.47s with 1 failure**. The green run does not erase archived first failures (Firefox sign-in interruption; WebKit rejected-tick persistence; WebKit admin sign-in interruption).
- Under 3 minutes is a goal, not proof that coverage must be cut.
- Worker-count experiments are authorized and unmeasured on this 486-case suite.
- No release-gate change: the suite remains Chromium + Firefox + WebKit. This matrix only stops running every detailed body on every engine.

Default 1-engine: **Chromium** (fastest of the three in the archived split: 490 call worker-s vs Firefox 578 / WebKit 561). Firefox and WebKit stay on every 3-engine row below.

Today `browser` in `browser_tests/conftest.py:38` is `params=["chromium", "firefox", "webkit"]`, so every `open_session` body is already 3-engine. Implementing this matrix needs a per-test opt-in, not a silent fixture default change.

Files **not** in this named set (`test_svelte_offline.py`, `offline_multidevice`, `offline_conflicts`, `timed_due_offline`, `rooms`, accessibility, admin, …) are **unchanged**. Several of those are already the WebKit storage/offline/conflict surface.

---

## 1. Recommended matrix

### Stay 3-engine — genuine engine-specific protection

These are not “unique journeys.” They hit storage, service worker, Unicode case-fold, keyboard/touch, live-stream cancel, or Playwright route/SW differences that the harness already special-cases for WebKit (`conftest.py` persistent profile for CacheStorage / Playwright #41618; `service_workers: "block"` because WebKit ignores `page.route` on a worker-controlled page; `set_offline` breaks WebKit navigation).

**Service worker / CacheStorage / persistent WebKit** (`test_svelte_service_worker.py`):
- `test_built_worker_takes_over_and_serves_a_cold_offline_deep_link`
- `test_real_build_swap_waits_for_a_stored_room_change` (IndexedDB queue + SW update)
- `test_waiting_version_takes_over_when_the_app_opens_offline`
- `test_coming_back_to_the_app_fetches_and_then_switches_version` (visibility + last-tab WebKit)
- `test_update_keeps_versions_while_an_uncontrolled_tab_is_open` (uncontrolled tab; persistent WebKit exits if the last tab closes)
- `test_interrupted_update_keeps_last_complete_version_usable`

**Offline snapshot / reconnect / revocation** (`test_svelte_offline_reconnect.py`):
- `test_typing_during_an_online_revalidation_does_not_filter` (`pageshow` / bfcache; Firefox and WebKit restore more aggressively than Chromium)
- `test_reconnect_needs_validation_and_feed_then_shows_other_devices_changes` (also the reconnect smoke)
- `test_revoked_password_clears_saved_room_on_reconnect` (IndexedDB clear)
- `test_reset_share_link_clears_only_that_saved_share` (share snapshot vs room snapshot isolation)
- `test_network_failure_and_5xx_on_revalidation_keep_the_snapshot`
- `test_foreground_resume_revalidates` (both `visibilitychange` and `pageshow`)
- `test_server_errors_without_a_snapshot_do_not_say_connect` (`storage_state` onto a new WebKit persistent profile)
- `test_losing_the_network_keeps_the_open_page_editable_then_back` (`set_offline`; documented WebKit navigation break)

**Keyboard + touch** (`test_svelte_items.py`):
- `test_suggestion_keyboard_tab_and_touch_selection`
- `test_usual_items_open_on_blank_focus_with_keyboard_and_touch` (expensive: 62.56 call worker-s across engines; stays because tap/keyboard/focus differ, not because usual-item ranking is engine-specific)

**Unicode case-fold + offline queue** (`test_svelte_items.py`):
- `test_offline_unicode_add_reconciles_to_the_server_mapping` (reads `String.toLowerCase` per engine)
- `test_offline_unicode_add_is_removed_after_server_rejection`

**Focus / keyboard in the due panel** (`test_svelte_due_center.py`):
- `test_bell_counts_overdue_and_today_and_groups_the_panel` (3-engine due-grouping smoke)
- `test_reveal_clears_the_search_and_focuses_the_item`
- `test_live_changes_update_the_open_panel_without_moving_focus` (`document.activeElement`)
- `test_bell_opens_and_closes_from_the_keyboard`
- `test_saved_panel_says_saved_and_offline_date_edits_count` (saved-view copy + offline date write)
- `test_zone_validation_online_and_offline` (offline half uses the saved view)

**Live stream / WebKit route** (`test_svelte_live.py`):
- `test_two_phones_see_each_others_changes` (EventSource; WebKit `/events` cancel is filtered in `conftest.py`)
- `test_password_change_revokes_open_pages`
- `test_rename_saved_after_a_password_change_changes_nothing` (explicitly blocks the worker so WebKit `page.route` works)

**Share stale-write after reset** (`test_svelte_share.py`):
- `test_visitor_views_and_edits_by_link_and_reset_stops_it` (3-engine share-isolation smoke)
- `test_writes_sent_after_a_reset_change_nothing` (`hold_live_updates` + WebKit route/SW)

**Stale deleted-list writes** (`test_svelte_deleted_lists.py`):
- Keep the **current** 3-engine file, including the existing room/public role alternation (`test_stale_page_cannot_write_after_list_deletion` and `test_stale_page_after_room_deletion_has_no_room_navigation`). This is already not a full action×role×engine cube. Teardown (66.2 worker-s) dominates; cutting engines is the wrong lever. WebKit live-stream hold is the same route/SW seam as share stale-write.

**Core list smoke** (also keyboard, dialog focus, click-outside, localStorage “show quantities” across reload):
- `test_add_restore_check_quantity_edit_and_undo`

### Detailed scenarios → 1 engine (Chromium), assertions retained in frontend/API + that one real journey

Unique browser behavior stays. Firefox/WebKit copies of the same Svelte wiring go away.

**Due-center rules / wiring** (`test_svelte_due_center.py`):
- `test_room_card_counts_what_is_due_in_the_list`
- `test_reload_shows_no_due_toast`
- `test_reveal_of_a_missing_item_says_so`
- `test_share_link_bell_shows_only_its_list`
- `test_bell_scope_follows_room_or_current_list`
- `test_whole_room_bell_ignores_another_room`
- `test_due_views_move_to_the_new_day_when_the_page_is_shown_again`
- `test_deleting_the_last_due_list_clears_the_room_bell`
- `test_reset_share_link_sends_the_old_link_to_unavailable`
- `test_timed_due_requires_zone_and_shows_server_confirmation`

**Item / tag / add-count rules** (`test_svelte_items.py`, `test_svelte_times_added.py`, `test_svelte_tags.py`):
- `test_add_trims_python_whitespace`
- `test_tags_filter_and_hide_done`
- `test_tag_colors_stay_and_letters_differ`
- `test_empty_list_hint_and_clear_tag_filter`
- `test_suggestions_rank_by_add_count_and_scroll`
- `test_item_dialog_counts_adds_and_unchecks`
- All seven bodies in `test_svelte_tags.py`

**Hide-done rules** (`test_svelte_hide_done.py`):
- `test_hide_done_modes_history_and_shared_updates`
- `test_hidden_count_line_under_the_list`

**Reconnect UI rule that is not storage** (`test_svelte_offline_reconnect.py`):
- `test_online_typing_only_suggests_and_never_filters`

**Live UI that is not stream/storage** (`test_svelte_live.py`):
- `test_suggestion_highlight_tracks_live_item_name`
- `test_list_deleted_while_open`
- `test_tag_deleted_elsewhere_stops_filtering`

**Share rights / dialogs already covered by API** (`test_svelte_share.py`):
- `test_repeated_resets_each_confirm_and_rotate_the_link`
- `test_invalid_links_show_no_list`
- `test_room_menu_shares_the_room_link`
- `test_visitor_edits_tags_but_cannot_rename_or_delete_the_list`
- `test_edits_and_tags_sent_after_a_reset_change_nothing`
- `test_a_room_member_gets_the_way_back_and_can_reset_on_the_share_page`
- `test_without_room_access_the_share_page_reveals_nothing_about_the_room`

**Stale-chunk recovery with service worker blocked** (`test_svelte_service_worker.py`; these are SvelteKit reload, not CacheStorage):
- `test_failed_link_click_opens_the_link_on_the_new_build`
- `test_unchanged_build_keeps_the_page`
- `test_failed_first_load_reloads_once_and_recovers`
- `test_chunk_that_stays_missing_shows_the_error_without_a_loop`

### One 3-engine smoke set

Exactly one representative of each non-engine product surface, plus the grouping UI the speed note already kept:

| Smoke | Body | Why this one |
| --- | --- | --- |
| Core list | `test_add_restore_check_quantity_edit_and_undo` | Combined add/check/undo/quantity/edit/dialog in a real engine |
| Share isolation | `test_visitor_views_and_edits_by_link_and_reset_stops_it` | Guest edits live, reset stops the old link, room stays closed |
| Offline reconnect | `test_reconnect_needs_validation_and_feed_then_shows_other_devices_changes` | Saved view, blocked feed, kept tick, then other-device merge |
| Due grouping UI | `test_bell_counts_overdue_and_today_and_groups_the_panel` | Real bell, badge, panel headings; math stays in unit tests |

Accounting: the four smoke bodies are also in the 3-engine keep list (`add_restore`, `visitor_views_and_edits_by_link_and_reset_stops_it`, `reconnect_needs_validation_and_feed_then_shows_other_devices_changes`, `bell_counts_overdue_and_today_and_groups_the_panel`). They are not extra cases. Do not add extra 3-engine copies of share-scoped bell, hide-done modes, or tag filter on top of them.

### Scale (named files only)

Current named-file cases ≈ 237 (due 48, items 30, reconnect 30, deleted 24, live 18, share 27, hide 6, tags 21, SW 30, times_added 3).

This matrix ≈ 157 cases in those files (~80 fewer cases, a **case-count estimate**, not measured elapsed savings; ~16% of the 486 passed suite). Worker-seconds are uneven: `add_restore` (65.83) and `usual_items` (62.56) stay 3-engine, so items-file elapsed barely moves. Due-center is the main named-file case-count drop (~20 of 48 cases). This matrix is **not expected** to reach 3 minutes. That is not a measured limit.

---

## 2. Assertion map (every 3→1 proposal)

Retained coverage is the **same browser body on Chromium** plus the faster layer. Nothing in this map deletes an assertion.

### Add-count — `test_item_dialog_counts_adds_and_unchecks`

| Old browser assertion | Retained |
| --- | --- |
| Dialog `Added once` / `Added 2 times` | `frontend/src/lib/list/items.test.ts` `addedLabel`; Chromium dialog journey |
| `Last added YYYY-MM-DD HH:MM` | `lastAddedLabel` in the same file; Chromium dialog |
| List row does not show “Added once” | Chromium journey only (layout) |
| Checking does not increment; unchecking does | `frontend/src/lib/data/add-count.test.ts` pending-ops + snapshot counts; Chromium checkbox+dialog |

### Due-center

| Old browser body | Faster retained | What the remaining Chromium journey still proves |
| --- | --- | --- |
| `test_room_card_counts_what_is_due_in_the_list` | `dueTally` in `due-reminders.test.ts`; `RoomLists.svelte` uses `dueTally` | Room-card “1 due” wiring |
| `test_reload_shows_no_due_toast` | Comment in file: toasts replaced; no due-toast unit | Bell still visible; no “due” toast |
| `test_reveal_of_a_missing_item_says_so` | none | “no longer on this list” copy |
| `test_share_link_bell_shows_only_its_list` | `tests/test_api_share.py` `test_share_feed_is_a_full_snapshot_of_only_the_shared_list` | Guest bell, no Whole-room / private-reminder controls |
| `test_bell_scope_follows_room_or_current_list` | `dueRows` / `.where` list names in `due-reminders.test.ts` | List vs room panel chrome |
| `test_whole_room_bell_ignores_another_room` | none for UI; server rooms are isolated | Chromium two-room bell |
| `test_due_views_move_to_the_new_day_when_the_page_is_shown_again` | `due-clock.svelte.test.ts` visibility/day rollover; `itemDueGroup` rollover in `due-reminders.test.ts` | Playwright clock + real panel heading |
| `test_deleting_the_last_due_list_clears_the_room_bell` | none for UI | Live delete → “none due” |
| `test_reset_share_link_sends_the_old_link_to_unavailable` | `tests/test_api_share.py` `test_reset_gives_a_new_link_and_blocks_the_old_one`, `test_share_stream_sends_seq_and_revoked_after_a_reset` | Unavailable page; bell gone |
| `test_timed_due_requires_zone_and_shows_server_confirmation` | `time-zone.test.ts` `validTime` / `canonicalTimeZone`; API due-time tests | Dialog confirmation + saved UTC line |

Grouping math for the **smoke** body stays in `dueGroupOfDay` / `dueSections` / `badgeText` / `dueTally`. The 3-engine smoke keeps the real bell/panel.

### Items / tags

| Old browser body | Faster retained |
| --- | --- |
| `test_add_trims_python_whitespace` | `normalizeItemName` in `items.test.ts` (`\u0085` included) |
| `test_tags_filter_and_hide_done` | `visible-items.test.ts` every-chosen-tag; `visibility.test.ts` `filterVisibleItems`; hide-done reload still in Chromium |
| `test_tag_colors_stay_and_letters_differ` | Chromium only (CSS `--tag`) |
| `test_empty_list_hint_and_clear_tag_filter` | Chromium only (empty copy + Clear chip) |
| `test_suggestions_rank_by_add_count_and_scroll` | `itemSuggestions` ranking in `items.test.ts`; Chromium scroll/viewport |
| `test_new_tags_come_from_options_not_the_tag_row` | Chromium Options > Tags |
| `test_tap_filters_the_items` | `visible-items.test.ts` tag filter |
| `test_options_click_opens_the_card_and_rename_keeps_the_filter` | `overlay.test.ts` `list.tag_rename`; Chromium filter-follows-rename |
| `test_recolor_and_delete_with_undo` | overlay tag_color / tag_remove; Chromium undo toast |
| `test_one_tag_mode_asks_first_and_keeps_the_first_tag` | overlay `list.tag_settings`; Chromium confirm dialog |
| `test_tag_settings_are_the_same_in_a_second_browser` | Chromium two-session; not engine storage |
| `test_edit_item_tag_chips_light_up_at_once` | overlay `item.toggle_tag`; Chromium Edit Item chips |

### Hide-done

| Old browser assertion | Retained |
| --- | --- |
| Modes All / After X days / Keep last X, zero rejected, numbers kept when switch goes off/on | `hide-done.test.ts` `parseHideDoneCount` / `hideDoneChange`; `visibility.test.ts` `filterVisibleItems` + `countHiddenChecked` (file comment: day boundaries already unit-tested) |
| Member + share visitor see the same mode live | Chromium two-session journey |
| Hidden item still searchable / restore unchecks | Chromium + `visible-items.test.ts` search vs hide-done |
| Hidden-count line text and live update | `countHiddenChecked`; Chromium line |

### Reconnect typing

| Old browser assertion | Retained |
| --- | --- |
| Online typing never filters the hide-done list | `visible-items.test.ts` “only suggests while online”; Chromium |

### Live UI

| Old browser body | Retained |
| --- | --- |
| `test_suggestion_highlight_tracks_live_item_name` | Chromium two-session combobox; ranking still in `itemSuggestions` |
| `test_list_deleted_while_open` | Chromium live delete UI; stale **write** stays 3-engine in `deleted_lists` |
| `test_tag_deleted_elsewhere_stops_filtering` | Chromium live chip removal |

### Share (API already owns the security rule)

| Old browser body | Retained |
| --- | --- |
| Repeated resets rotate the token | `test_reset_gives_a_new_link_and_blocks_the_old_one`; Chromium confirm/toast |
| Invalid links show no list | `test_invalid_tokens_reveal_nothing` |
| Room menu share dialog | Chromium dialog copy |
| Visitor can tag, cannot rename/delete/reset | `test_share_holder_edits_items_tags_and_hide_done`; `test_share_link_cannot_change_the_room_or_the_list_itself` |
| Edit/tag after reset change nothing | `test_reset_blocks_a_retry_of_an_op_sent_before`; 3-engine `writes_sent_after_a_reset` still covers undo/add after hold |
| Member back-arrow + reset on share page | `test_room_member_reads_the_share_link`; Chromium Decision 146 UI |
| Share page leaks no room slug/name | `test_share_feed_reveals_nothing_about_the_room_without_access`; `test_a_member_who_clears_the_cookie_gets_nothing`; Chromium `page.content()` check |

### Stale chunks (SW blocked)

Same four Playwright bodies on Chromium. No CacheStorage assertion in them. Frontend `service-worker.test.ts` covers visibility/update policy, not the 404-reload loop.

---

## 3. Risks

**WebKit storage / offline (do not regress these):**
- Ephemeral CacheStorage does not survive page replacement; tests use a disposable persistent profile (`conftest.py:117–122`, `docs/browser-testing.md`). All six SW takeover tests stay 3-engine.
- Persistent WebKit exits when the last tab closes (`test_svelte_service_worker.py:31–32`, `_wait_for_controlled_page`). Uncontrolled-tab and cold-offline-deep-link stay 3-engine.
- Playwright cannot intercept API calls of a worker-controlled WebKit page. Reconnect tests already run with `service_workers: "block"` (`test_svelte_offline_reconnect.py:21–24`). They prove IndexedDB saved views, **not** SW-controlled fetch. Cutting them to 1 engine would drop Firefox/WebKit IndexedDB + `storage_state` onto a persistent profile.
- `set_offline` breaks WebKit navigation; reconnect uses `route.abort()` except `test_losing_the_network_*`, which stays 3-engine.
- Linux WebKit is the Safari evidence (`plans/test-suite-speed.md` 2026-10-18). This matrix still runs WebKit on SW, snapshots, unicode, keyboard/touch, live revoke, and the four smokes.

**Acceptable residual (1-engine):**
- Share-scoped bell, room vs list scope, other-room bell: app JS + server isolation, not engine storage. Cross-room UI has no frontend twin; Chromium is the remaining wiring check.
- Hide-done / tag filter / add-count **rules**: unit-tested. Live two-session hide-done is Chromium-only.
- Playwright `page.clock` + visibility day-rollover: unit-tested in `due-clock.svelte.test.ts`; real-page clock APIs can differ. Residual flake risk, not a security hole.
- `test_suggestion_highlight_tracks_live_item_name` (34.91 call worker-s): unique live combobox, not unique engine. ARIA live updates on Firefox/WebKit are the residual.
- Stale-chunk 404 reload on Firefox/WebKit is residual; SW update path stays 3-engine.
- Deleted-lists stays 3-engine; if a later pass cuts it, run **both roles on Chromium** so role coverage does not shrink with the current alternation.

**Cost residual:** `usual_items` is the second-largest body and stays 3-engine. If this matrix is approved but that one cost is rejected, the only tight fallback is Chromium-only `usual_items`, because `test_suggestion_keyboard_tab_and_touch_selection` already keeps keyboard+touch on three engines. Do not drop both.

**Process:** 120 P2 skips stay skipped. Archived first failures stay visible. No new skips, retries, or timeouts as speed tools.

---

## 4. Worker-count before any matrix cut: **yes**

Worker-count is authorized and unmeasured on this suite. Documented local command is `-n 4` (`docs/browser-testing.md`). Historical 2-vs-4 work was a ~52-case suite, not 486. Current 4-worker efficiency ≈ 3.94 on the archived 622s run, so four workers are saturated; **6 and 8 are unknown**, including RAM.

Measure on the **current** toast-dismiss candidate (486 passed / 557.65s), one heavy job at a time, before implementing engine cuts:

- `-n 4` repeat (comparability)
- `-n 6` and `-n 8` (pytest default for the Python suite is 8; browser docs warn not to inherit it blindly)
- `-n 2` only as a RAM/CPU sanity bound

Record elapsed, pass/fail/skip, teardown errors, and peak RSS. If 6/8 OOM or teardown-fail, that is the resource reason to stay at 4. If they are clean, keep the higher count **and then** apply this matrix.

Do not skip that measurement because a matrix exists. Workers do not change coverage. The matrix does. Helper cuts already cannot reach 3 minutes; 557s / 180s ≈ 3.1×, which would need ~12 linear workers and is not claimed here. Workers first tells the owner how much of the gap is hardware vs coverage.

---

## 5. Owner trade-off (approve or reject this matrix)

**Approve** if you want three engines only where engines actually differ (WebKit CacheStorage/SW, IndexedDB snapshots, bfcache resume, Unicode `toLowerCase`, keyboard/touch/focus, live-stream cancel, stale-write with `page.route`), and you accept that detailed due / add-count / hide-done / tag / share-rights **rules** run once in Chromium with frontend/API still owning the permutations. Firefox and WebKit remain in the suite. The release gate does not change. This is not expected to produce a 3-minute run.

**Reject** if you want every current journey to keep proving Firefox and WebKit even when the rule is already unit-tested. That is a coverage preference. It is not a speed plan. Helpers cannot get there; this matrix cannot get there either; unmeasured workers should still be tried either way.

Do not implement until worker-count on the 557.65s candidate is sampled, unless you explicitly want the coverage change first. Coordinate with the in-flight browser-verify job; one heavy browser command at a time.