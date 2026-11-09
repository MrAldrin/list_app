# Change-based test selection map

2026-11-09 · lr-005.1.2 · inspected baseline `integration` = `6d4b0dcb`.
**Proposal, not an implemented selector.** Selected tests give early feedback;
they do not replace the completion checks in [AGENTS.md](../../AGENTS.md).
No prerequisite task is recorded on this bead. No product or test code changed.

## Evidence and map

Evidence: imports, routers, fixtures, routes and selectors.
`tests/api_helpers.py` uses `main.app`; `tests/conftest.py` resets schema and
sign-in limits. Direct imports alone miss these dependencies.
`browser_tests/conftest.py` builds Svelte and runs real servers in Chromium,
Firefox and WebKit. Browser rows show route/interaction coverage, not imports.

Notation: Python names below mean `tests/test_<name>.py`; browser names mean
`browser_tests/test_<name>.py`. Braces mean a union, not a literal filename.
Frontend paths start at `frontend/src/`; unit tests are adjacent `*.test.ts`
unless a path is given. Rows are starting sets, not proven minimal sets.
**Existing coverage gap:** `svelte_policy_editor` is skipped at module level;
`svelte_private_reminders` skips personal-settings cases (only the public-share
no-controls check is active). These rows identify intended coverage, not active
settings verification. The [standing pause](../testing.md#known-limits) needs S3;
this task does not change skips. Most components use browser coverage; only
`ItemDialog.test.ts` directly mounts a component in the inspected unit suite.

| Source area | Python tests to start with | Browser coverage / reason |
| --- | --- | --- |
| `src/api/{ops,changes,events,idempotency}.py`, `live_updates.py` | `api_{item_ops,list_ops,tag_ops,tag_settings,changes,events,idempotency,conflicts,concurrency}`, `change_tracking`, `share_seq`, `deletion_pruning`, `write_atomicity_cross_path` | `svelte_{items,tags,live,share,deleted_lists,offline,offline_conflicts,offline_multidevice,offline_reconnect,timed_due_offline}`; `/ops`, `/changes`, `/events` cross all views. Full-suite trigger. |
| `src/api/{access,session,room,share,admin,invitations,cookies,sign_in_limit}.py`; `admin_access`, `room_cookies`, `room_invitations`, `password_hashing`, `sign_in_limiter`, `identifiers` | `api_{basics,session,room,share,admin,admin_session,invitations}`, `cookie_headers`, `room_{cookies,invitations,password_minimum,token_validation}`, `rooms`, `password_{hashes,checks_outside_lock}`, `public_share_tokens`, `sign_in_{limiter,rate_limit}` | `svelte_{rooms,room_management,room_switcher,admin,invitations,share,restart,offline}`, `browser_sessions`; member/public/admin boundaries. Full-suite trigger. |
| `src/database_crud.py`, `database_setup.py`, `migrations.py` | All `tests/`; useful diagnostics: `database_{crud,setup}`, `migrations`, `*_migration`, `item_ids`, `write_atomicity_cross_path` | All browser tests depend on server storage. Full-suite trigger, including schema changes in setup rather than only `migrations.py`. |
| `src/{item_names,item_visibility,field_limits}.py` | `item_{name_capitalization_migration,uniqueness,renames,edits,visibility}`, `api_name_case`, `list_{names,renames}`, `field_{limits,rules_migration}`, `count_limits`, `quantity_updates`, `tags`, `times_added`, `api_{item_ops,list_ops,tag_ops,tag_settings}` | `svelte_{items,item_sort,hide_done,tags,times_added,share}`; shared validation affects room and public writes. Full-suite trigger. |
| `src/reminders/{due_schedule,zoned_time,rules,policies,preview}.py` | `reminders_{zoned_time,rules,policies,preview}`, `item_{date,due_time}`, `due_cycle_start`, `api_reminders`, `api_reminders_review` | `svelte_{item_date,due_center,due_center_phone,policy_editor,timed_due_offline}`; due schedule also enters ops, feeds and undo. |
| `src/reminders/identity.py`, `src/api/{reminders,reminder_policies}.py` | `api_reminders`, `api_reminders_review`, `reminders_policies`, `reminders_identity_migration`, `due_cycle_start` | `svelte_{private_reminders,policy_editor,due_center,room_management}`; enrollment cookie, private policy routes, revocation. Identity/auth changes require full suite. |
| `src/{main,server,config,security_headers,health,svelte_frontend}.py`; `src/api/{__init__,requests,errors,version}.py` | `config`, `security_headers`, `healthz`, `server_shutdown`, `svelte_frontend_routes`, `api_{basics,version}`, `deletion_pruning` | All pages/API use app wiring, origin checks and asset routing. Full-suite trigger. |
| `src/{pwa_routes,install_manifest}.py`, `src/static/` | `pwa_routes`, `svelte_frontend_routes` | `old_service_worker`, `svelte_{install_browser,service_worker,old_urls}`; manifests and `/sw.js` legacy removal. Full-suite trigger for routing/cache changes. |
| `scripts/{deploy_backup,seed_test_data,serve_svelte_local,build_docs_site}.py` | Respectively `deploy_backup`, `seed_test_data`, `serve_svelte_local`, `docs_site_build` (direct imports; backup test fakes Railway/jj) | No browser suite needed for an isolated script-only change. These tests do not approve or perform deployment. |
| `scripts/generate_app_icons.py` | No dedicated test found | Generated icons are served by PWA routes; use `pwa_routes`, install browser tests and inspect generated output. Do not treat lack of a direct test as no checks needed. |

| Frontend source area | Unit starting set | Browser starting set |
| --- | --- | --- |
| `lib/data/` transport, feeds, stores, queue, snapshots, session lifecycle and shared `types.ts` | All `lib/data/*.test.ts`, including `index`, `room-store`, `room-lifetime.svelte`, `offline-integration`, `api`, `events`, `share`, `write-queue`, `queue-storage`, `overlay`, `rebase`, `snapshot-{store,validate}`, `compat` | All browser tests: `index.ts` is the component entry point and imports queue/store/session/feed behavior. Full-suite trigger, including helpers without same-name tests such as `feed`, `backoff`, `standalone-session`, `session-transition`, `room-signin`. |
| `lib/list/` components and pure view helpers | `items`, `tags`, `hide-done`, `hold-order`, `search`, `reveal`, `visible-items`, `ItemDialog`, `time-zone`, `due-reminders`, `due-clock.svelte`; also data `item-date`, `add-count`, `visibility`, `order` | `svelte_{items,item_sort,item_date,tags,hide_done,times_added,deleted_lists,due_center,due_center_phone,timed_due_offline,share}`; `.row` and named item/tag dialogs exercise these paths. |
| `lib/reminders/` | `api`, `rule-edit`, `rules`; list `due-reminders`, `due-clock.svelte` | `svelte_{private_reminders,policy_editor,due_center,due_center_phone}`; “Enroll this device”, “Personal item reminders”, “Save policy”, “Preview next five”. No dedicated unit tests found for `personal-reminders` or `device-zone.svelte`. |
| `lib/room/`, `lib/admin/`, `lib/invitation/`, `lib/room-link.ts` | `room/remembered-rooms`, `admin/{admin-links,invitations}`, `room-link`; data `{admin,invitation,last-room,room-lifetime.svelte}` | `svelte_{rooms,room_management,room_switcher,admin,invitations,share,restart}`, `browser_sessions`; route shells and login/create/reset/delete dialogs. Auth/lifecycle edits require full suite. |
| `lib/ui/`, `app.css`, `app.html` | `ui/{theme,theme.svelte,toasts,share,field-limits}`, `app-colors` | `svelte_{theme,toasts,dialog,bottom_bar,accessibility,tap_targets,phone_fixes,compat}` plus consumers of an edited shared dialog/menu. Global CSS, shell or shared primitives require full suite. |
| `lib/install/`, `service-worker.ts`, `lib/{service-worker,worker-routes,stale-build}.ts`, `hooks.client.ts` | `install/manifest`, `service-worker`, `worker-routes`, `stale-build` | `svelte_{install_browser,service_worker,offline,offline_multidevice,restart,compat}`, `old_service_worker`; cache/upgrade/error recovery crosses every route. Unit tests cover page-side coordination and route classification, not the worker cache/fetch implementation directly. Full-suite trigger. |
| `routes/` (`/`, `/room/[slug]`, nested list, `/list/[slug]`, `/share/[token]`, `/admin`, `/create-room/[token]`), layouts/error page | Imported helper tests above; no route-level unit suite found | `svelte_{rooms,old_urls,share,admin,invitations,compat,service_worker}` plus feature consumers. Layout/navigation/error handling requires full suite. |

## Always run the full suite

Use the full Python suite, all frontend unit tests and the full three-engine
browser suite for the shared-code triggers above. Also use it for dependency or
build/test configuration, fixture/helper changes, API contracts, unknown paths,
new source files, deletions and renames. Apply the widest rule when rows overlap.
This conservative policy avoids trusting a static import map for dynamic routes,
SQL, selectors and indirect effects. Do not limit shared `ops.py` changes to one
operation's tests merely because its edit looks local.

“Full” here means `uv run pytest -q`, `npm test` in `frontend/`, and the browser
command in the [browser guide](../browser-testing.md), under the night-loop lock:
`flock /home/hsa/.local/state/night-loop/list_app/browser.lock uv run pytest browser_tests -q -n 4`.
Keep lint, type and build checks required by [the frontend guide](../../frontend/README.md)
and AGENTS.md. Android is a separate opt-in suite, not part of plain pytest:
include `android_tests/test_android_chrome.py` for install, persisted login and
network-recovery changes when the documented emulator is ready. It does not
substitute for WebKit or the offline browser cases; see [Android limits](../android-emulator-testing.md).

## Selection proposal (no new dependencies)

1. Later, build a standard-library Python **print-only** selector. Use
   `jj --no-pager diff --from <base> --to @ --name-only`; default to accepted
   `integration`, not `@-` (which misses earlier feature commits). Print the
   resolved base ID. Read a summary too: deletion/rename, failed commands or
   ambiguous output force full mode, never an empty test set.
2. Use reviewed explicit path rules, not stem matching. Union matching rows,
   expand globs, sort, deduplicate and check test existence. Unknown/new source
   or zero-match rules force full mode. Test-only changes select those tests;
   shared helpers/config force full mode. Known prose-only paths need no product
   tests; preview inputs select `tests/test_docs_site_build.py`.
3. Print paths, reasons, files and commands. Use argument arrays, explicit pytest
   paths and `npm test -- <paths>` relative to `frontend/`. Browser selections
   retain all engines, `-n 4` and the lock. An empty diff means “no changes”, not
   “tests passed”.
4. Validate synthetic cases: local script/theme/reminder; shared data/schema/auth/
   worker; mixed areas; test/helper; prose; unknown/new/deleted/renamed path;
   invalid base; empty diff. Compare with full runs on real changes. Do not
   reduce completion gates without this evidence and owner approval.

Prefer this transparent table to new pytest markers: markers still need manual
maintenance and cannot select Vitest or browser coverage by themselves.
`pytest-testmon` is an optional future comparison, not installed or proposed as
a required dependency; it would not cover Svelte/browser relationships alone.

**Limits:** static inspection, not measured execution coverage. No tests were run
for this one-file research change; no selector was written. Existing test results
on other bookmarks do not prove this baseline passes. Component rows group
indirect coverage; missing direct unit tests are not proof of no browser coverage.
