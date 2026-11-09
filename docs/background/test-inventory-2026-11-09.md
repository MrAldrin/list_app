# Test inventory — 9 November 2026

Scope: `integration` `ltoqrxzw` / `6d4b0dcb`. One row per test file;
no product or test changes. This is an inventory, not an assertion audit or
permission to remove coverage. Engine sensitivity is a conservative file-level
assessment: **yes** = a real engine/platform seam is exercised; **no** = no
real engine is exercised; **unknown** = UI wiring or DOM simulation without
proof that engine differences matter. A yes does not mean every body needs
three engines. The proposed per-body matrix is separate and unaccepted.

## Evidence and units

- **P**: measured aggregate testcase worker-seconds (setup/call/teardown), from
  archived `python-baseline.xml` / `browser-baseline.xml`, 5 November. These
  are **not** file wall times and must not be added to predict suite elapsed.
- **V**: measured Vitest file span in seconds, from attempt 1 on 9 November,
  `/tmp/lr-005-vitest.json`. Files overlap. Counts include parameter expansion;
  browser counts include engines and intentional skips. **D** means declared
  Python bodies (Android), not collected parameter-expanded cases.
- Attempt 1 Python: **1,783 passed, 9 skipped**, 53.84 s; collection 1,792.
  The nine frontend-build skips remain visible. Per-file Python costs use the
  older XML, not estimates from the new suite wall time.
- Attempt 1 frontend under UTC: **1,112 passed, 2 failed**, 1,114 total.
  `due-reminders.test.ts` fails on local-day and confirmed-deadline boundaries.
  No rerun, timezone repair, retry or new skip was used here.
- Archived browser baseline: **484 passed, 2 failed, 120 skipped**, 662.37 s
  command elapsed. Sign-in interruption (Firefox accessibility) and rejected
  tick lost after reload (WebKit conflicts) remain failures, not clean passes.
  No browser or Android execution in this task. Android runtime is unmeasured.
- Sources: [runtime report](../reports/test-suite-runtime-2026-11-05.md),
  [speed decision](test-suite-speed.md), [review evidence](test-suite-review.md).
  Also read `browser-suite-speed-2026-11-08.md` and
  `engine-matrix-review-2026-11-08.md` at bookmark `lr-gt2-checkpoint`.
  They are absent from this base. The speed report confirms unchanged test
  and product sources between the archived baseline and this base. Its final
  browser sample (one failure) is distinct from the XML sample used below.

Cost flags: **P** = inherited `clean_db` and `fresh_sign_in_limits`, with one
production-cost `home_password_hash` per Python worker; **B** = fresh disposable
server, browser/context setup, build check (build if stale), always-on traces,
screenshots and API-idle teardown. `hash/auth` identifies direct auth/hash
work by source/name, not a measured phase attribution. `param` is explicit
parameterization; `wait/poll` is a source-level wait, not a proposed workaround.
IDB uses simulated storage in frontend tests. No registered slow marker was
found; existing skip/skipif markers and counts are retained below.

## Five most expensive measured file groups

All five are browser groups from the same baseline XML. Ranking uses aggregate
worker-seconds, not elapsed time. Android cannot be ranked without measurement.

| File | Cases | Worker-s | Protection |
| --- | ---: | ---: | --- |
| `browser_tests/test_svelte_due_center.py` | 48 | 359.71 | due bell, grouping, scope and live panel |
| `browser_tests/test_svelte_items.py` | 30 | 269.09 | real UI add/check/edit/delete/undo |
| `browser_tests/test_svelte_offline_reconnect.py` | 30 | 161.38 | saved views, validation, revocation and recovery |
| `browser_tests/test_svelte_deleted_lists.py` | 24 | 152.00 | stale writes after list/room deletion |
| `browser_tests/test_svelte_live.py` | 18 | 130.95 | two-session live updates and focus |

## Per-file inventory

Protection labels name the source area, not a coverage guarantee. Paths are
relative to the repository root. Frontend “unit/state” includes pure rules and
state/reducer tests; “component” uses Svelte mounting; “integration” joins
offline queue/storage flows. Python service rows can also touch SQLite through
the shared fixture. No runtime value below is an estimate.

### Python (74 files)

| File | Layer | Tests | Runtime s | Product area protected | Engine-sensitive | Cost fixtures/markers |
| --- | --- | ---: | ---: | --- | --- | --- |
| `tests/test_api_admin.py` | API | 50 | P 8.83 | api admin | no | P, param |
| `tests/test_api_admin_session.py` | API | 43 | P 1.26 | api admin session | no | P, param |
| `tests/test_api_basics.py` | API | 44 | P 3.57 | api basics | no | P, param |
| `tests/test_api_changes.py` | API | 33 | P 9.22 | api changes | no | P, param |
| `tests/test_api_concurrency.py` | API | 11 | P 6.70 | api concurrency | no | P |
| `tests/test_api_conflicts.py` | API | 35 | P 6.94 | stale edits and explicit conflict handling | no | P |
| `tests/test_api_events.py` | API | 17 | P 7.87 | live event feed and access changes | no | P |
| `tests/test_api_idempotency.py` | API | 224 | P 59.31 | operation replay, duplicate writes and room boundaries | no | P, param |
| `tests/test_api_invitations.py` | API | 49 | P 5.35 | invitation acceptance and access boundaries | no | P, param |
| `tests/test_api_item_ops.py` | API | 75 | P 15.88 | api item ops | no | P, param |
| `tests/test_api_list_ops.py` | API | 53 | P 11.57 | api list ops | no | P, param, wait/poll |
| `tests/test_api_name_case.py` | API | 11 | P 2.16 | api name case | no | P, param |
| `tests/test_api_reminders.py` | API | 48 | P 12.31 | reminder enrollment, access and operations | no | P, param |
| `tests/test_api_reminders_review.py` | API | 15 | P 5.15 | api reminders review | no | P |
| `tests/test_api_room.py` | API | 39 | P 15.71 | room access, isolation and list ownership | no | P, param |
| `tests/test_api_session.py` | API | 27 | P 4.75 | api session | no | P, param |
| `tests/test_api_share.py` | API | 36 | P 5.64 | public token access, revocation and isolation | no | P, param |
| `tests/test_api_tag_ops.py` | API | 40 | P 8.67 | api tag ops | no | P, param |
| `tests/test_api_tag_settings.py` | API | 40 | P 7.77 | api tag settings | no | P, param |
| `tests/test_api_version.py` | API | 42 | P 0.09 | api version | no | P, param |
| `tests/test_change_tracking.py` | Python rules/service | 47 | P 1.45 | change tracking | no | P, param |
| `tests/test_config.py` | Python rules/service | 19 | P 1.96 | config | no | P, process/server, param |
| `tests/test_cookie_headers.py` | Python rules/service | 8 | P 1.41 | cookie headers | no | P |
| `tests/test_count_limits.py` | Python rules/service | 18 | P 1.73 | count limits | no | P, hash/auth, param |
| `tests/test_database_crud.py` | DB/migration | 18 | P 7.73 | database crud | no | P, hash/auth, param |
| `tests/test_database_setup.py` | DB/migration | 16 | P 3.20 | database setup | no | P, hash/auth, process/server, param |
| `tests/test_deletion_pruning.py` | Python rules/service | 8 | P 1.45 | deletion pruning | no | P, wait/poll |
| `tests/test_deploy_backup.py` | process/tool | 37 | P 0.70 | deploy backup | no | P, process/server, param |
| `tests/test_docs_site_build.py` | process/tool | 31 | P 3.30 | docs site build | no | P, process/server, param |
| `tests/test_due_cycle_start.py` | Python rules/service | 23 | P 4.21 | due cycle start | no | P, param |
| `tests/test_field_limits.py` | Python rules/service | 20 | P 3.75 | field limits | no | P, param |
| `tests/test_field_rules_migration.py` | DB/migration | 64 | P 13.08 | field rules migration | no | P, param |
| `tests/test_healthz.py` | process/tool | 3 | P 0.04 | healthz | no | P |
| `tests/test_item_date.py` | Python rules/service | 27 | P 5.12 | item date | no | P, param |
| `tests/test_item_due_time.py` | Python rules/service | 36 | P 5.77 | item due time | no | P, param |
| `tests/test_item_edits.py` | Python rules/service | 8 | P 1.56 | item edits | no | P, param |
| `tests/test_item_ids.py` | Python rules/service | 9 | P 0.43 | item ids | no | P, param |
| `tests/test_item_name_capitalization_migration.py` | DB/migration | 7 | P 1.40 | item name capitalization migration | no | P |
| `tests/test_item_renames.py` | Python rules/service | 2 | P 0.00 | item renames | no | P |
| `tests/test_item_undo.py` | Python rules/service | 4 | P 0.00 | item undo | no | P |
| `tests/test_item_uniqueness.py` | Python rules/service | 2 | P 0.00 | item uniqueness | no | P |
| `tests/test_item_visibility.py` | Python rules/service | 16 | P 0.02 | item visibility | no | P, param |
| `tests/test_list_names.py` | Python rules/service | 7 | P 1.53 | list names | no | P, param |
| `tests/test_list_renames.py` | Python rules/service | 3 | P 0.00 | list renames | no | P |
| `tests/test_migrations.py` | DB/migration | 11 | P 0.15 | migrations | no | P |
| `tests/test_offline_schema_migration.py` | DB/migration | 6 | P 1.34 | offline schema migration | no | P |
| `tests/test_password_checks_outside_lock.py` | Python rules/service | 5 | P 4.42 | password checks outside lock | no | P, hash/auth |
| `tests/test_password_hashes.py` | Python rules/service | 23 | P 9.16 | password hashes | no | P, hash/auth, param |
| `tests/test_positive_visibility_migration.py` | DB/migration | 15 | P 3.28 | positive visibility migration | no | P, param |
| `tests/test_public_share_tokens.py` | Python rules/service | 1 | P 0.19 | public share tokens | no | P |
| `tests/test_pwa_routes.py` | Python rules/service | 17 | P 0.07 | pwa routes | no | P, param |
| `tests/test_quantity_updates.py` | Python rules/service | 9 | P 0.02 | quantity updates | no | P, param |
| `tests/test_reminders_identity_migration.py` | DB/migration | 5 | P 1.09 | reminders identity migration | no | P |
| `tests/test_reminders_policies.py` | Python rules/service | 33 | P 7.21 | reminders policies | no | P, param |
| `tests/test_reminders_preview.py` | Python rules/service | 11 | P 0.01 | reminders preview | no | P |
| `tests/test_reminders_rules.py` | Python rules/service | 43 | P 0.02 | reminders rules | no | P, param |
| `tests/test_reminders_zoned_time.py` | Python rules/service | 21 | P 0.04 | reminders zoned time | no | P, process/server, param |
| `tests/test_room_cookies.py` | Python rules/service | 9 | P 0.01 | room cookies | no | P, param |
| `tests/test_room_invitations.py` | Python rules/service | 19 | P 6.07 | room invitations | no | P, param |
| `tests/test_room_password_minimum.py` | Python rules/service | 17 | P 2.31 | room password minimum | no | P, hash/auth, param |
| `tests/test_room_token_validation.py` | Python rules/service | 8 | P 3.32 | room token validation | no | P, param |
| `tests/test_rooms.py` | Python rules/service | 14 | P 3.92 | rooms | no | P, param |
| `tests/test_security_headers.py` | Python rules/service | 7 | P 0.47 | security headers | no | P, param |
| `tests/test_seed_test_data.py` | process/tool | 5 | P 0.99 | seed test data | no | P |
| `tests/test_serve_svelte_local.py` | process/tool | 12 | P 0.26 | serve svelte local | no | P |
| `tests/test_server_shutdown.py` | process/tool | 1 | P 2.12 | server shutdown | no | P, process/server |
| `tests/test_share_seq.py` | Python rules/service | 8 | P 0.76 | share seq | no | P |
| `tests/test_sign_in_limiter.py` | Python rules/service | 10 | P 0.01 | sign in limiter | no | P, hash/auth |
| `tests/test_sign_in_rate_limit.py` | Python rules/service | 13 | P 34.48 | room/global limits with real password hashing | no | P, hash/auth |
| `tests/test_svelte_frontend_routes.py` | Python rules/service | 60 | P 0.27 | frontend routes | no | P, 9 skipped, param |
| `tests/test_tag_settings_migration.py` | DB/migration | 11 | P 2.55 | tag settings migration | no | P, param |
| `tests/test_tags.py` | Python rules/service | 11 | P 2.09 | tags | no | P, param |
| `tests/test_times_added.py` | Python rules/service | 21 | P 4.15 | times added | no | P, param |
| `tests/test_write_atomicity_cross_path.py` | DB/migration | 1 | P 0.19 | write atomicity cross path | no | P |

### Frontend (54 files)

| File | Layer | Tests | Runtime s | Product area protected | Engine-sensitive | Cost fixtures/markers |
| --- | --- | ---: | ---: | --- | --- | --- |
| `frontend/src/app-colors.test.ts` | unit/state | 474 | V 0.028 | app colors | no | — |
| `frontend/src/lib/admin/admin-links.test.ts` | unit/state | 1 | V 0.002 | admin links | no | — |
| `frontend/src/lib/admin/invitations.test.ts` | unit/state | 3 | V 0.003 | invitations | no | — |
| `frontend/src/lib/data/add-count.test.ts` | unit/state | 9 | V 0.006 | add count | no | — |
| `frontend/src/lib/data/admin.test.ts` | unit/state | 9 | V 0.038 | admin | no | — |
| `frontend/src/lib/data/api.test.ts` | unit/state | 13 | V 0.044 | api | no | — |
| `frontend/src/lib/data/compat.test.ts` | unit/state | 8 | V 0.030 | compat | no | — |
| `frontend/src/lib/data/events.test.ts` | unit/state | 17 | V 0.038 | events | no | fake clock |
| `frontend/src/lib/data/ids.test.ts` | unit/state | 4 | V 0.016 | ids | no | — |
| `frontend/src/lib/data/index.test.ts` | unit/state | 24 | V 0.321 | index | unknown | IDB, fake clock |
| `frontend/src/lib/data/invitation.test.ts` | unit/state | 3 | V 0.035 | invitation | no | — |
| `frontend/src/lib/data/item-date.test.ts` | unit/state | 24 | V 0.011 | item date | no | — |
| `frontend/src/lib/data/last-room.test.ts` | unit/state | 4 | V 0.007 | last room | no | — |
| `frontend/src/lib/data/not-saved.test.ts` | unit/state | 13 | V 0.005 | not saved | no | — |
| `frontend/src/lib/data/offline-integration.test.ts` | integration | 59 | V 6.455 | durable queues, replay, conflicts and sign-out guards | unknown | IDB, fake clock, queue/storage integration |
| `frontend/src/lib/data/order.test.ts` | unit/state | 16 | V 0.009 | order | no | — |
| `frontend/src/lib/data/overlay.test.ts` | unit/state | 43 | V 0.011 | overlay | no | — |
| `frontend/src/lib/data/queue-storage.test.ts` | unit/state | 18 | V 0.169 | queue storage | unknown | IDB |
| `frontend/src/lib/data/rebase.test.ts` | unit/state | 13 | V 0.006 | rebase | no | — |
| `frontend/src/lib/data/result.test.ts` | unit/state | 8 | V 0.005 | result | no | — |
| `frontend/src/lib/data/room-lifetime.svelte.test.ts` | component | 2 | V 0.008 | room lifetime | no | — |
| `frontend/src/lib/data/room-store.test.ts` | unit/state | 38 | V 0.030 | room store | no | — |
| `frontend/src/lib/data/share.test.ts` | unit/state | 9 | V 0.048 | share | no | — |
| `frontend/src/lib/data/snapshot-store.test.ts` | unit/state | 15 | V 0.041 | snapshot store | unknown | IDB |
| `frontend/src/lib/data/snapshot-validate.test.ts` | unit/state | 3 | V 0.004 | snapshot validate | no | — |
| `frontend/src/lib/data/status.test.ts` | unit/state | 10 | V 0.014 | status | no | — |
| `frontend/src/lib/data/visibility.test.ts` | unit/state | 24 | V 0.013 | visibility | no | — |
| `frontend/src/lib/data/write-queue.test.ts` | unit/state | 24 | V 0.048 | write queue | no | fake clock |
| `frontend/src/lib/install/manifest.test.ts` | unit/state | 11 | V 0.004 | manifest | no | — |
| `frontend/src/lib/list/ItemDialog.test.ts` | unit/state | 1 | V 0.027 | ItemDialog | unknown | — |
| `frontend/src/lib/list/due-clock.svelte.test.ts` | component | 5 | V 0.021 | day rollover at mount and visibility changes | unknown | fake clock |
| `frontend/src/lib/list/due-reminders.test.ts` | unit/state | 14 | V 0.031 | due-day groups and confirmed-instant boundaries | no | RED: 2 failures |
| `frontend/src/lib/list/hide-done.test.ts` | unit/state | 8 | V 0.005 | hide done | no | — |
| `frontend/src/lib/list/hold-order.test.ts` | unit/state | 7 | V 0.006 | hold order | no | — |
| `frontend/src/lib/list/items.test.ts` | unit/state | 25 | V 0.010 | item labels, suggestions and edit rules | no | — |
| `frontend/src/lib/list/reveal.test.ts` | unit/state | 3 | V 0.003 | reveal | no | — |
| `frontend/src/lib/list/search.test.ts` | unit/state | 6 | V 0.004 | search | no | — |
| `frontend/src/lib/list/tags.test.ts` | unit/state | 24 | V 0.008 | tags | no | — |
| `frontend/src/lib/list/time-zone.test.ts` | unit/state | 4 | V 0.085 | time zone | no | — |
| `frontend/src/lib/list/visible-items.test.ts` | unit/state | 9 | V 0.005 | visible items | no | — |
| `frontend/src/lib/reminders/api.test.ts` | unit/state | 8 | V 0.047 | api | no | — |
| `frontend/src/lib/reminders/rule-edit.test.ts` | unit/state | 2 | V 0.003 | rule edit | no | — |
| `frontend/src/lib/reminders/rules.test.ts` | unit/state | 2 | V 0.003 | rules | no | — |
| `frontend/src/lib/room/remembered-rooms.test.ts` | unit/state | 13 | V 0.006 | remembered rooms | no | — |
| `frontend/src/lib/room-link.test.ts` | unit/state | 15 | V 0.004 | room link | no | — |
| `frontend/src/lib/service-worker.test.ts` | unit/state | 14 | V 0.155 | service worker | no | — |
| `frontend/src/lib/setup.test.ts` | unit/state | 1 | V 0.002 | setup | no | — |
| `frontend/src/lib/stale-build.test.ts` | unit/state | 7 | V 0.006 | stale build | no | — |
| `frontend/src/lib/ui/field-limits.test.ts` | unit/state | 3 | V 0.003 | field limits | no | — |
| `frontend/src/lib/ui/share.test.ts` | unit/state | 6 | V 0.006 | share | no | — |
| `frontend/src/lib/ui/theme.svelte.test.ts` | component | 7 | V 0.019 | theme | unknown | — |
| `frontend/src/lib/ui/theme.test.ts` | unit/state | 10 | V 0.005 | theme | no | — |
| `frontend/src/lib/ui/toasts.test.ts` | unit/state | 8 | V 0.013 | toasts | no | fake clock |
| `frontend/src/lib/worker-routes.test.ts` | unit/state | 13 | V 0.004 | worker routes | no | — |

### Browser (37 files)

| File | Layer | Tests | Runtime s | Product area protected | Engine-sensitive | Cost fixtures/markers |
| --- | --- | ---: | ---: | --- | --- | --- |
| `browser_tests/test_browser_sessions.py` | browser | 9 | P 19.72 | native storage isolation and profile cleanup | yes | B, contexts, param |
| `browser_tests/test_old_service_worker.py` | browser | 3 | P 11.58 | old service worker | yes | B, contexts |
| `browser_tests/test_svelte_accessibility.py` | browser | 12 | P 48.86 | accessibility | yes | B, contexts, RED baseline |
| `browser_tests/test_svelte_admin.py` | browser | 6 | P 27.41 | admin | unknown | B, contexts |
| `browser_tests/test_svelte_bottom_bar.py` | browser | 3 | P 12.48 | bottom bar | unknown | B, contexts, wait/poll |
| `browser_tests/test_svelte_compat.py` | browser | 9 | P 46.38 | compat | yes | B, contexts, wait/poll |
| `browser_tests/test_svelte_deleted_lists.py` | browser | 24 | P 152.00 | stale writes after list/room deletion | yes | B, contexts, param |
| `browser_tests/test_svelte_dialog.py` | browser | 6 | P 13.81 | dialog | yes | B, contexts, param |
| `browser_tests/test_svelte_due_center.py` | browser | 48 | P 359.71 | due bell, grouping, scope and live panel | unknown | B, contexts |
| `browser_tests/test_svelte_due_center_phone.py` | browser | 6 | P 48.02 | due center phone | yes | B, contexts, param |
| `browser_tests/test_svelte_hide_done.py` | browser | 6 | P 63.30 | hide done | unknown | B, contexts |
| `browser_tests/test_svelte_install_browser.py` | browser | 9 | P 18.78 | install browser | yes | B, contexts |
| `browser_tests/test_svelte_invitations.py` | browser | 6 | P 17.19 | invitations | unknown | B, contexts |
| `browser_tests/test_svelte_item_date.py` | browser | 3 | P 21.27 | item date | unknown | B, contexts |
| `browser_tests/test_svelte_item_sort.py` | browser | 6 | P 33.85 | item sort | yes | B, contexts, wait/poll |
| `browser_tests/test_svelte_items.py` | browser | 30 | P 269.09 | real UI add/check/edit/delete/undo | unknown | B, contexts |
| `browser_tests/test_svelte_live.py` | browser | 18 | P 130.95 | two-session live updates and focus | unknown | B, contexts |
| `browser_tests/test_svelte_offline.py` | browser | 15 | P 112.46 | saved views and offline UI actions | yes | B, contexts, wait/poll |
| `browser_tests/test_svelte_offline_conflicts.py` | browser | 15 | P 104.48 | durable rejection and explicit retry consent | yes | B, contexts, RED baseline, wait/poll |
| `browser_tests/test_svelte_offline_multidevice.py` | browser | 27 | P 119.80 | offline edits merged across devices | yes | B, contexts, wait/poll |
| `browser_tests/test_svelte_offline_reconnect.py` | browser | 30 | P 161.38 | saved views, validation, revocation and recovery | yes | B, contexts, param, wait/poll |
| `browser_tests/test_svelte_old_urls.py` | browser | 18 | P 40.01 | old urls | unknown | B, contexts |
| `browser_tests/test_svelte_phone_fixes.py` | browser | 9 | P 27.61 | phone fixes | yes | B, contexts |
| `browser_tests/test_svelte_policy_editor.py` | browser | 18 | P 0.00 | policy editor | unknown | B, contexts, 18 skipped |
| `browser_tests/test_svelte_private_reminders.py` | browser | 105 | P 10.88 | private reminders | unknown | B, contexts, 102 skipped, param, skip |
| `browser_tests/test_svelte_restart.py` | browser | 6 | P 36.63 | restart | unknown | B, contexts |
| `browser_tests/test_svelte_room_management.py` | browser | 9 | P 52.67 | room management | unknown | B, contexts, param |
| `browser_tests/test_svelte_room_switcher.py` | browser | 15 | P 55.58 | room switcher | unknown | B, contexts |
| `browser_tests/test_svelte_rooms.py` | browser | 15 | P 94.55 | rooms | unknown | B, contexts, param |
| `browser_tests/test_svelte_service_worker.py` | browser | 30 | P 63.90 | service worker | yes | B, contexts, wait/poll |
| `browser_tests/test_svelte_share.py` | browser | 27 | P 112.00 | share | unknown | B, contexts |
| `browser_tests/test_svelte_tags.py` | browser | 21 | P 84.78 | tags | unknown | B, contexts |
| `browser_tests/test_svelte_tap_targets.py` | browser | 3 | P 23.81 | tap targets | yes | B, contexts |
| `browser_tests/test_svelte_theme.py` | browser | 18 | P 31.88 | theme | yes | B, contexts, param |
| `browser_tests/test_svelte_timed_due_offline.py` | browser | 12 | P 77.86 | timed due offline | yes | B, contexts |
| `browser_tests/test_svelte_times_added.py` | browser | 3 | P 50.86 | times added | unknown | B, contexts |
| `browser_tests/test_svelte_toasts.py` | browser | 6 | P 56.33 | toasts | unknown | B, contexts |

### Android (1 files)

| File | Layer | Tests | Runtime s | Product area protected | Engine-sensitive | Cost fixtures/markers |
| --- | --- | ---: | ---: | --- | --- | --- |
| `android_tests/test_android_chrome.py` | Android | 2 D | unmeasured | password prompt, install, remembered access and recovery | yes | ADB/emulator; install/CDP/network recovery, wait/poll |

## Limits and checks

File discovery covers `tests/test_*.py`, `frontend/src/**/*.test.ts`,
`browser_tests/test_*.py` and `android_tests/test_*.py`; helper/conftest files
are cost inputs, not test groups. All Python collection counts match archived
XML file counts. All frontend result paths match current test files. Static
body counts are not substituted for parameter-expanded counts except Android.
The 120 browser skips are the existing P2 settings cases, not speed cuts.
No product check was repeated: known red runs are input evidence, not a failed
check of this documentation change. Document checks verify complete path
coverage, count totals and only one new tracked file. No separate reviewer
was configured. Later tiering must retain security, durable edits, live/offline
and platform-specific protection; this inventory does not choose tiers.
